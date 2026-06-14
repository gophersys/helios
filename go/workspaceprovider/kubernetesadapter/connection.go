package kubernetesadapter

import (
	"bytes"
	"context"
	stderrors "errors"
	"io"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/workspaceprovider"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	executil "k8s.io/client-go/util/exec"
)

// connection is the kubernetes workspaceprovider.Connection: Run/Exec/Files/Probe over one
// workspace pod. It is THIN — the library owns the state machine, the one-primary-workload
// gate, and status normalization; this drives the apiserver (the SPDY exec plane and the pod
// read).
type connection struct {
	adapter   *Adapter
	namespace string
	pod       string
	handle    workspaceprovider.Handle
}

// Static assertion: *connection satisfies the workspaceprovider.Connection port.
var _ workspaceprovider.Connection = (*connection)(nil)

// connection builds the Connection over a workspace pod.
func (a *Adapter) connection(namespace, pod string, handle workspaceprovider.Handle) *connection {
	return &connection{adapter: a, namespace: namespace, pod: pod, handle: handle}
}

// Run launches the primary workload as an exec INTO the workspace pod's hold container (the pod
// model: the pod is the workspace, the exec is the workload). The resolved workload credential
// is injected per the spec's Vehicle at the injection site only — env on the child for
// VehicleEnv, a tmpfs file for VehicleFile — never logged, never in the spec. The exec runs to
// completion in a goroutine; its combined output is buffered for Run.Logs replay and its exit
// signal rides Run.Status (mirrors the docker adapter's exec-as-workload model so the
// conformance suite is substrate-transparent).
//
//nolint:gocritic,ireturn // contract §2: Run takes spec/resolved by value AND returns the RunDriver port; the surface is frozen.
func (c *connection) Run(ctx context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) (workspaceprovider.RunDriver, error) {
	command, ierr := c.injectCredential(ctx, spec, resolved)
	if ierr != nil {
		return nil, ierr
	}
	driver := &runDriver{done: make(chan struct{})}
	// Run the workload exec asynchronously: Run returns once the process is LAUNCHED (not once
	// it exits), exactly like the docker adapter. The buffered output + terminal status are
	// read by Run.Logs / Run.Status. context.WithoutCancel detaches the workload from the Run
	// call's ctx so a returned Run keeps executing (its lifecycle is bounded by Teardown).
	go func() {
		var combined syncBuffer
		err := c.adapter.client.Exec(context.WithoutCancel(ctx), ExecRequest{
			Namespace: c.namespace,
			Pod:       c.pod,
			Container: workspaceContainer,
			Command:   command,
			Stdout:    &combined,
			Stderr:    &combined,
			TTY:       spec.TTY,
		})
		driver.finish(combined.Bytes(), exitCodeOf(err))
	}()
	return driver, nil
}

// Exec runs ONE command to completion in the workspace pod and returns its real exit code +
// bounded output. A timeout is enforced by ctx; the library maps a deadline to DeadlineError.
//
//nolint:gocritic // contract §2 fixes Connection.Exec's spec by value; the port surface is frozen.
func (c *connection) Exec(ctx context.Context, spec workspaceprovider.ExecSpec) (workspaceprovider.ExecResult, error) {
	if spec.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, spec.Timeout)
		defer cancel()
	}
	var stdout, stderr bytes.Buffer
	err := c.adapter.client.Exec(ctx, ExecRequest{
		Namespace: c.namespace,
		Pod:       c.pod,
		Container: workspaceContainer,
		Command:   spec.Command,
		Stdin:     spec.Stdin,
		Stdout:    &stdout,
		Stderr:    &stderr,
		TTY:       spec.TTY,
	})
	exitCode, fatal := classifyExec(err)
	if fatal != nil {
		if ctx.Err() != nil {
			return workspaceprovider.ExecResult{}, &workspaceprovider.DeadlineError{Op: "Exec"}
		}
		return workspaceprovider.ExecResult{}, classifyAPIError("exec", fatal)
	}
	// Writing to the caller's sinks is best-effort: a sink write error is the CALLER's concern
	// (their writer), not the exec's; the buffered bytes still ride ExecResult.
	if spec.Stdout != nil {
		_, _ = spec.Stdout.Write(stdout.Bytes()) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stdout.
	}
	if spec.Stderr != nil {
		_, _ = spec.Stderr.Write(stderr.Bytes()) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stderr.
	}
	return workspaceprovider.ExecResult{
		ExitCode: exitCode,
		Stdout:   stdout.Bytes(),
		Stderr:   stderr.Bytes(),
		Detail:   "kubernetes exec",
	}, nil
}

// Files returns the kubernetes file seam (tar-over-exec: Put streams a tar into `tar -x`, Get
// streams `tar -c` out, List runs an `ls` exec).
//
//nolint:ireturn // contract §2: Connection.Files returns the Files port; the surface is frozen.
func (c *connection) Files() workspaceprovider.Files {
	return &files{conn: c, handle: c.handle}
}

// Probe reads the pod's live state and normalizes it. The library stamps Since and owns the
// State machine; this reports the native reading (the pod phase, the OOMKilled/Evicted typed
// conditions, the native reason verbatim in Detail).
func (c *connection) Probe(ctx context.Context) (workspaceprovider.Probe, error) {
	pod, err := c.adapter.client.GetPod(ctx, c.namespace, c.pod)
	if err != nil {
		if apierrors.IsNotFound(err) {
			return workspaceprovider.Probe{State: workspaceprovider.StateGone, Detail: "pod not found"}, nil
		}
		return workspaceprovider.Probe{}, classifyAPIError("probe pod", err)
	}
	return normalizeProbe(pod), nil
}

// normalizeProbe maps a pod's native status onto a workspaceprovider Probe: the phase becomes a
// State, OOMKilled/Evicted container terminations become typed Conditions, and the native
// reason rides Detail verbatim (never a normalized field).
func normalizeProbe(pod *corev1.Pod) workspaceprovider.Probe {
	if podIsTerminating(pod) {
		return workspaceprovider.Probe{State: workspaceprovider.StateGone, Detail: "terminating"}
	}
	probe := workspaceprovider.Probe{State: workspaceprovider.StateReady, Detail: string(pod.Status.Phase)}
	switch pod.Status.Phase {
	case corev1.PodRunning:
		probe.State = workspaceprovider.StateReady
	case corev1.PodPending:
		probe.State = workspaceprovider.StateProvisioning
	case corev1.PodSucceeded, corev1.PodFailed:
		probe.State = workspaceprovider.StateGone
	case corev1.PodUnknown:
		probe.State = workspaceprovider.StateDegraded
	}
	if reason := pod.Status.Reason; reason != "" {
		probe.Detail = reason
		if strings.EqualFold(reason, "Evicted") {
			probe.State = workspaceprovider.StateEvicted
			probe.Conditions = append(probe.Conditions, workspaceprovider.ConditionEvicted)
		}
	}
	for i := range pod.Status.ContainerStatuses {
		applyContainerCondition(&probe, &pod.Status.ContainerStatuses[i])
	}
	return probe
}

// applyContainerCondition folds a single container's terminated reason into the probe's State +
// Conditions (an OOMKilled termination is the runaway-agent signal, 02 §2). It checks both the
// current and last-termination state so a restart-on-OOM is still surfaced.
func applyContainerCondition(probe *workspaceprovider.Probe, status *corev1.ContainerStatus) {
	terminations := []*corev1.ContainerStateTerminated{status.State.Terminated, status.LastTerminationState.Terminated}
	for _, term := range terminations {
		if term != nil && strings.EqualFold(term.Reason, "OOMKilled") {
			probe.State = workspaceprovider.StateDegraded
			probe.Detail = "OOMKilled"
			probe.Conditions = append(probe.Conditions, workspaceprovider.ConditionOOMKilled)
			return
		}
	}
}

// runDriver is the kubernetes RunDriver: it reports the workload exec's terminal status and
// replays the buffered output for Logs. The exec runs in a goroutine launched by Run; finish
// records the result and closes done so Status returns the terminal phase deterministically.
type runDriver struct {
	done   chan struct{}
	once   sync.Once
	buffer []byte
	code   int
}

// Static assertion: *runDriver satisfies workspaceprovider.RunDriver.
var _ workspaceprovider.RunDriver = (*runDriver)(nil)

// finish records the workload's combined output + exit code and signals terminal exactly once.
func (r *runDriver) finish(output []byte, code int) {
	r.once.Do(func() {
		r.buffer = output
		r.code = code
		close(r.done)
	})
}

// sigkillExitCode is a process killed by SIGKILL (128+9) — the exit code the kubelet/runtime
// reports when the workload's memory cgroup OOM-kills it (the limit binds; the kernel kills the
// over-memory workload). The exec-into-hold model means the OOM REASON ("OOMKilled") attaches to
// the exec'd child, not the long-lived hold container, so the real Run path surfaces the kill as
// a SIGKILL exit → RunKilled (real ENFORCEMENT, faithful), but NOT the ConditionOOMKilled
// discriminator (a documented limitation — contract §7 amendment + OD-15).
const sigkillExitCode = 137

// Status blocks until the workload's exec finishes (or ctx fires), then returns the terminal
// phase with the real exit code; ok=false at terminal/cancellation. A SIGKILL exit (137 — the
// kernel killing an over-memory workload, the real cgroup enforcement) is RunKilled, not a
// generic RunFailed, so caseResourceLimits observes the real enforcement on k8s; a non-zero
// non-kill exit is RunFailed; zero is RunSucceeded.
func (r *runDriver) Status(ctx context.Context) (workspaceprovider.RunStatus, bool) {
	select {
	case <-r.done:
		return workspaceprovider.RunStatus{Phase: phaseForExit(r.code), ExitCode: r.code, Detail: "kubernetes exec exited"}, false
	case <-ctx.Done():
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, false
	}
}

// phaseForExit maps a workload exit code onto a terminal RunPhase: 0 is Succeeded, a SIGKILL
// (137 — an OOM-kill or a forced kill) is RunKilled (the workload was aborted, not a clean
// failure), and any other non-zero is RunFailed.
func phaseForExit(code int) workspaceprovider.RunPhase {
	switch code {
	case 0:
		return workspaceprovider.RunSucceeded
	case sigkillExitCode:
		return workspaceprovider.RunKilled
	default:
		return workspaceprovider.RunFailed
	}
}

// Logs replays the workload's combined output buffered at exec time, from the cursor. It blocks
// until the workload finishes so the full buffer is available (the exec-as-workload model
// buffers rather than tails; CapLogStream is honored by replaying the captured stream from a
// cursor).
func (r *runDriver) Logs(ctx context.Context, from workspaceprovider.LogCursor) (io.ReadCloser, error) {
	select {
	case <-r.done:
	case <-ctx.Done():
		return nil, &workspaceprovider.DeadlineError{Op: "Run.Logs"}
	}
	// The cursor is a uint64; bounds-check it AS a uint64 against the buffer length BEFORE the int
	// conversion, so a cursor past the buffer (or one that would overflow int) clamps to the end
	// rather than wrapping into a negative index (a real bounds check on the log-replay load path).
	start := len(r.buffer)
	if uint64(from) < uint64(len(r.buffer)) {
		start = int(from) // #nosec G115 -- guarded: from < len(buffer) (an int), so the value provably fits in int; gosec cannot follow the uint64 guard.
	}
	return io.NopCloser(bytes.NewReader(r.buffer[start:])), nil
}

// classifyExec splits an exec error into (exitCode, fatal): a CodeExitError/ExitError is the
// command's real non-zero exit (exitCode set, fatal nil); a nil error is exit 0; anything else
// is a fatal transport/apiserver error.
func classifyExec(err error) (exitCode int, fatal error) {
	if err == nil {
		return 0, nil
	}
	var codeErr executil.CodeExitError
	if stderrors.As(err, &codeErr) {
		return codeErr.ExitStatus(), nil
	}
	var exitErr executil.ExitError
	if stderrors.As(err, &exitErr) {
		return exitErr.ExitStatus(), nil
	}
	return 0, err
}

// exitCodeOf extracts the exit code from a workload exec error for Run.Status: a non-zero exit
// is the command's code; a transport error reports a non-zero (1) so the workload reads as
// Failed rather than silently Succeeded.
func exitCodeOf(err error) int {
	code, fatal := classifyExec(err)
	if fatal != nil {
		return 1
	}
	return code
}

// syncBuffer is a goroutine-safe bytes.Buffer: the Run exec writes from its own goroutine while
// Run.Logs may read concurrently, so the buffer guards its writes with a mutex (the race
// detector flags an unguarded bytes.Buffer shared across goroutines).
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	n, _ := s.buf.Write(p) // bytes.Buffer.Write never returns a non-nil error (it only grows).
	return n, nil
}

func (s *syncBuffer) Bytes() []byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]byte(nil), s.buf.Bytes()...)
}
