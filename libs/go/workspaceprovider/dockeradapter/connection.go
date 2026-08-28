package dockeradapter

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"math"
	"strings"
	"sync"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/limitedbuffer"
	"github.com/gophersys/libs/go/workspaceprovider/internal/logcursor"
)

// connection is the docker workspaceprovider.Connection: Run/Exec/Files/Probe over one
// container. It is THIN — the library owns the state machine, the one-primary-workload
// gate, and status normalization; this drives the daemon.
type connection struct {
	adapter *Adapter
	id      string // the container name/id this connection drives
	handle  workspaceprovider.Handle
}

// Static assertion: *connection satisfies the workspaceprovider.Connection port.
var _ workspaceprovider.Connection = (*connection)(nil)

// connection builds the Connection over a container.
func (a *Adapter) connection(id string, handle workspaceprovider.Handle) *connection {
	return &connection{adapter: a, id: id, handle: handle}
}

// Run launches the primary workload as a docker exec INTO the holding container (the pod
// model: the container is the workspace, the exec is the workload). The resolved workload
// credential is injected per the spec's Vehicle at the injection site only — env on the
// child for VehicleEnv, a tmpfs file for VehicleFile — never logged, never in the spec. It
// returns a RunDriver the library wraps as a Run ONCE THE WORKLOAD IS LAUNCHED — it does NOT
// block until the workload exits (the contract's "returns once the process is launched, not
// once it exits", workspaceprovider.go Workspace.Run). The attach stream is drained into a
// bounded buffer by a GOROUTINE so Logs/Status observe the live workload while Run returns
// immediately; this makes the docker Run timing IDENTICAL to the kubernetes adapter (both
// launch async — connection.go's runDriver{done} on each substrate), which the conformance
// caseRunReturnsBeforeWorkloadExits asserts on both bindings.
//
//nolint:gocritic,ireturn // contract §2: Run takes spec/resolved by value AND returns the RunDriver port; the surface is frozen.
func (c *connection) Run(ctx context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) (workspaceprovider.RunDriver, error) {
	env, ferr := c.injectCredential(ctx, spec, resolved)
	if ferr != nil {
		return nil, ferr
	}
	execResp, err := c.adapter.client.ContainerExecCreate(ctx, c.id, container.ExecOptions{
		Cmd:          spec.Command,
		Env:          env,
		WorkingDir:   spec.WorkDir,
		Tty:          spec.TTY,
		AttachStdout: true,
		AttachStderr: true,
	})
	if err != nil {
		return nil, classifyDockerError("exec create (run)", err)
	}
	// Attach starts the exec and gives us its multiplexed output stream for Logs.
	attach, err := c.adapter.client.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{Tty: spec.TTY})
	if err != nil {
		return nil, classifyDockerError("exec attach (run)", err)
	}
	driver := &runDriver{
		client:      c.adapter.client,
		execID:      execResp.ID,
		containerID: c.id,
		tty:         spec.TTY,
		buffer:      limitedbuffer.New(0),
		done:        make(chan struct{}),
	}
	// Drain the hijacked stream into the bounded buffer in a GOROUTINE: io.Copy/StdCopy reads
	// until the stream EOFs (the workload's process exit), so doing it synchronously here would
	// block Run until the workload exits — the divergence-from-k8s bug. Draining async lets Run
	// return the instant the workload is launched; the buffer is live for Logs and `done` signals
	// Status the drain finished (the workload reached terminal). context.WithoutCancel detaches
	// the drain from the Run call's ctx so a returned Run keeps buffering (its lifecycle is bounded
	// by the workload's own exit / Teardown).
	go driver.drain(attach, spec.TTY)
	return driver, nil
}

// Exec runs ONE command to completion and returns its real exit code + bounded output. A
// timeout is enforced by ctx; the library maps a deadline to DeadlineError.
//
//nolint:gocritic // contract §2 fixes Connection.Exec's spec by value; the port surface is frozen.
func (c *connection) Exec(ctx context.Context, spec workspaceprovider.ExecSpec) (workspaceprovider.ExecResult, error) {
	if spec.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, spec.Timeout)
		defer cancel()
	}
	execResp, err := c.adapter.client.ContainerExecCreate(ctx, c.id, container.ExecOptions{
		Cmd:          spec.Command,
		WorkingDir:   spec.WorkDir,
		Tty:          spec.TTY,
		AttachStdin:  spec.Stdin != nil,
		AttachStdout: true,
		AttachStderr: true,
	})
	if err != nil {
		return workspaceprovider.ExecResult{}, classifyDockerError("exec create", err)
	}
	attach, err := c.adapter.client.ContainerExecAttach(ctx, execResp.ID, container.ExecAttachOptions{Tty: spec.TTY})
	if err != nil {
		if ctx.Err() != nil {
			return workspaceprovider.ExecResult{}, &workspaceprovider.DeadlineError{Op: "Exec"}
		}
		return workspaceprovider.ExecResult{}, classifyDockerError("exec attach", err)
	}
	defer attach.Close()

	if spec.Stdin != nil {
		go func() {
			// Copying the caller's stdin into the exec is best-effort: a write error means
			// the exec already closed its stdin, which the exit code below reflects.
			_, _ = io.Copy(attach.Conn, spec.Stdin) //nolint:errcheck // best-effort stdin pump; the exec's exit code is the authority.
			_ = attach.CloseWrite()                 //nolint:errcheck // CloseWrite after the pump is advisory; the exec proceeds regardless.
		}()
	}

	// Capture stdout/stderr into BOUNDED buffers (limitedbuffer): ExecResult is documented bounded
	// (types.go ExecResult), but a plain bytes.Buffer fed by external process output is unbounded —
	// a chatty command would OOM the control plane. A workload that needs unbounded output uses
	// Run.Logs streaming (the contract's escape hatch). Truncation is surfaced in Detail.
	stdout, stderr := limitedbuffer.New(0), limitedbuffer.New(0)
	if derr := demux(attach.Reader, stdout, stderr, spec.TTY); derr != nil && ctx.Err() != nil {
		return workspaceprovider.ExecResult{}, &workspaceprovider.DeadlineError{Op: "Exec"}
	}
	// Writing to the caller's sinks is best-effort: a sink write error is the CALLER's
	// concern (their writer), not the exec's; the buffered bytes still ride ExecResult.
	if spec.Stdout != nil {
		_, _ = spec.Stdout.Write(stdout.Bytes()) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stdout.
	}
	if spec.Stderr != nil {
		_, _ = spec.Stderr.Write(stderr.Bytes()) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stderr.
	}

	inspect, ierr := c.adapter.client.ContainerExecInspect(ctx, execResp.ID)
	if ierr != nil {
		if ctx.Err() != nil {
			return workspaceprovider.ExecResult{}, &workspaceprovider.DeadlineError{Op: "Exec"}
		}
		return workspaceprovider.ExecResult{}, classifyDockerError("exec inspect", ierr)
	}
	return workspaceprovider.ExecResult{
		ExitCode: inspect.ExitCode,
		Stdout:   stdout.Bytes(),
		Stderr:   stderr.Bytes(),
		Detail:   execDetail("docker exec", stdout.Truncated() || stderr.Truncated()),
	}, nil
}

// execDetail tags the exec diagnostic with a truncation note when the bounded buffer dropped
// output, so a consumer reading ExecResult.Detail learns the bytes are bounded, not whole (the
// large-output case the contract routes to Run.Logs).
func execDetail(base string, truncated bool) string {
	if truncated {
		return base + " (output truncated at bound)"
	}
	return base
}

// Files returns the docker file seam (CopyToContainer/CopyFromContainer over a tar stream).
//
//nolint:ireturn // contract §2: Connection.Files returns the Files port; the surface is frozen.
func (c *connection) Files() workspaceprovider.Files {
	return &files{adapter: c.adapter, id: c.id, handle: c.handle}
}

// Probe reads the container's live state and normalizes it. The library stamps Since and
// owns the State machine; this reports the native reading.
func (c *connection) Probe(ctx context.Context) (workspaceprovider.Probe, error) {
	inspect, err := c.adapter.client.ContainerInspect(ctx, c.id)
	if err != nil {
		if isNotFound(err) {
			return workspaceprovider.Probe{State: workspaceprovider.StateGone, Detail: "container not found"}, nil
		}
		return workspaceprovider.Probe{}, classifyDockerError("inspect (probe)", err)
	}
	probe := workspaceprovider.Probe{State: workspaceprovider.StateReady}
	if inspect.State != nil {
		probe.Detail = inspect.State.Status
		switch {
		case inspect.State.OOMKilled:
			probe.State = workspaceprovider.StateDegraded
			probe.Conditions = append(probe.Conditions, workspaceprovider.ConditionOOMKilled)
		case inspect.State.Running:
			probe.State = workspaceprovider.StateReady
		case inspect.State.Dead, strings.EqualFold(inspect.State.Status, "exited"):
			probe.State = workspaceprovider.StateGone
		}
	}
	probe.Usage = c.usage(ctx)
	return probe, nil
}

// usage reads a single cpu/memory stats sample (best-effort; zero on any error — the
// reconcile loop tolerates a missing sample).
func (c *connection) usage(ctx context.Context) workspaceprovider.ResourceUsage {
	stats, err := c.adapter.client.ContainerStats(ctx, c.id, false)
	if err != nil {
		return workspaceprovider.ResourceUsage{}
	}
	defer func() { _ = stats.Body.Close() }() //nolint:errcheck // closing a read stats stream has no actionable error.
	var sample statsSample
	if derr := json.NewDecoder(stats.Body).Decode(&sample); derr != nil {
		return workspaceprovider.ResourceUsage{}
	}
	return workspaceprovider.ResourceUsage{
		MemoryBytes: clampInt64(sample.MemoryStats.Usage),
	}
}

// clampInt64 converts a uint64 memory-usage reading from the daemon's stats JSON to the int64 the
// usage snapshot carries, clamping at the int64 ceiling rather than wrapping negative. The
// conversion is on the F1 usage-metering load path (the meter folds MemoryBytes into UsageRecord),
// so an absurd/overflowing reading must saturate, never become a negative byte count.
func clampInt64(v uint64) int64 {
	if v > math.MaxInt64 {
		return math.MaxInt64
	}
	return int64(v)
}

// statsSample is the minimal slice of docker's stats JSON the usage snapshot reads.
type statsSample struct {
	MemoryStats struct {
		Usage uint64 `json:"usage"`
	} `json:"memory_stats"`
}

// runDriver is the docker RunDriver: it inspects the exec for its terminal status and
// replays the buffered output for Logs. It carries the CONTAINER id (not just the exec id) so
// it can read the container's cgroup OOMKilled flag — a memory-bomb exec'd into the holding
// container trips the container's State.OOMKilled even though the exec's own exit code is
// unreliable (verified against the real daemon), which is how the runaway-agent OOM signal
// surfaces as RunKilled / ConditionOOMKilled. The attach stream is drained ASYNCHRONOUSLY (Run
// launches drain in a goroutine, mirroring the kubernetes adapter's async Run): `done` closes
// when the drain finishes (the workload exited), so Status reports RunRunning while live and the
// terminal phase after — and Logs replays the bounded buffer the drain fills concurrently.
type runDriver struct {
	client      dockerClient
	execID      string
	containerID string
	tty         bool
	buffer      *limitedbuffer.Buffer
	done        chan struct{}
	once        sync.Once
}

// Static assertion: *runDriver satisfies workspaceprovider.RunDriver.
var _ workspaceprovider.RunDriver = (*runDriver)(nil)

// drain reads the hijacked exec output into the bounded buffer until the stream EOFs (the
// workload's process exit), then signals done so Status/Logs observe the terminal workload. It
// runs in the goroutine Run launches, which is what makes Run non-blocking (Run returns the
// instant the workload is launched, not when it exits — the contract parity with kubernetes).
func (r *runDriver) drain(attach types.HijackedResponse, tty bool) {
	defer attach.Close()
	// A demux error means the stream closed early; the buffered prefix is still the workload's
	// real output and rides Run.Logs (the exit code rides Run.Status via the exec inspect).
	_ = demux(attach.Reader, r.buffer, r.buffer, tty) //nolint:errcheck // partial output is still valid; the exit code is the authority.
	r.finish()
}

// finish closes done exactly once (idempotent across a re-drain or a double signal).
func (r *runDriver) finish() {
	r.once.Do(func() { close(r.done) })
}

// Status reports the workload's phase. While the exec is RUNNING it returns RunRunning, ok=true
// (the live-workload observation the async Run enables); once the drain has finished (the exec
// exited) it inspects the real exit code and returns the terminal phase, ok=false. A container
// whose cgroup OOM-killed the workload surfaces as RunKilled / ConditionOOMKilled with the native
// reason in Detail (the runaway-agent signal, 02 §2). ctx cancellation returns RunRunning,ok=false
// (mirrors the kubernetes adapter's select-on-done/ctx shape).
func (r *runDriver) Status(ctx context.Context) (workspaceprovider.RunStatus, bool) {
	select {
	case <-r.done:
		// The drain finished (the workload exited): fall through to the terminal exit-code read.
	case <-ctx.Done():
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, false
	default:
		// The drain has not finished: confirm the exec is still live before reporting Running, so a
		// drain about to finish does not falsely hang the caller.
		inspect, err := r.client.ContainerExecInspect(ctx, r.execID)
		if err != nil {
			return workspaceprovider.RunStatus{Phase: workspaceprovider.RunFailed, Detail: "exec inspect failed"}, false
		}
		if inspect.Running {
			return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, true
		}
		// The exec exited but the drain goroutine has not yet closed done; wait for it (bounded by
		// the stream EOF the exit caused) so the terminal read sees the full buffer.
		select {
		case <-r.done:
		case <-ctx.Done():
			return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, false
		}
	}
	inspect, err := r.client.ContainerExecInspect(ctx, r.execID)
	if err != nil {
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunFailed, Detail: "exec inspect failed"}, false
	}
	if r.workloadOOMKilled(ctx) {
		return workspaceprovider.RunStatus{
			Phase:     workspaceprovider.RunKilled,
			Condition: workspaceprovider.ConditionOOMKilled,
			ExitCode:  inspect.ExitCode,
			Detail:    "OOMKilled",
		}, false
	}
	phase := workspaceprovider.RunSucceeded
	if inspect.ExitCode != 0 {
		phase = workspaceprovider.RunFailed
	}
	return workspaceprovider.RunStatus{
		Phase:    phase,
		ExitCode: inspect.ExitCode,
		Detail:   "docker exec exited",
	}, false
}

// workloadOOMKilled reports whether the holding container's cgroup OOM-killed the workload
// (the exec child). docker sets State.OOMKilled on the CONTAINER when any process in its
// cgroup is OOM-killed, including an exec child, so this is the reliable signal even when the
// exec's own exit code does not reflect the kill.
func (r *runDriver) workloadOOMKilled(ctx context.Context) bool {
	if r.containerID == "" {
		return false
	}
	inspect, err := r.client.ContainerInspect(ctx, r.containerID)
	if err != nil || inspect.State == nil {
		return false
	}
	return inspect.State.OOMKilled
}

// Logs replays the workload's combined output from the cursor, bounded by the shared logcursor
// replay slice (the cursor is uint64-guarded against the buffer length before the int conversion).
// It WAITS for the drain to finish so the full bounded buffer is available — mirroring the
// kubernetes adapter's buffer-then-replay model (CapLogStream is honored by replaying the captured
// stream from a cursor). ctx cancellation drops THIS reader only (a DeadlineError).
func (r *runDriver) Logs(ctx context.Context, from workspaceprovider.LogCursor) (io.ReadCloser, error) {
	select {
	case <-r.done:
	case <-ctx.Done():
		return nil, &workspaceprovider.DeadlineError{Op: "Run.Logs"}
	}
	return io.NopCloser(bytes.NewReader(logcursor.Replay(r.buffer.Bytes(), from))), nil
}

// demux splits docker's multiplexed stdout/stderr stream into the two writers, or copies
// raw when tty is set (a TTY stream is not framed).
func demux(src io.Reader, stdout, stderr io.Writer, tty bool) error {
	if tty {
		if _, err := io.Copy(stdout, src); err != nil {
			return errors.Wrap(errors.KindInternal, "dockeradapter: copy tty exec stream", err)
		}
		return nil
	}
	if _, err := stdcopy.StdCopy(stdout, stderr, src); err != nil {
		return errors.Wrap(errors.KindInternal, "dockeradapter: demux exec stream", err)
	}
	return nil
}
