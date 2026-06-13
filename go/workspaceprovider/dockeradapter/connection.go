package dockeradapter

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"strings"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
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
// returns a RunDriver the library wraps as a Run.
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
		client: c.adapter.client,
		execID: execResp.ID,
		tty:    spec.TTY,
	}
	driver.buffer = drainHijack(attach, spec.TTY)
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

	var stdout, stderr bytes.Buffer
	if derr := demux(attach.Reader, &stdout, &stderr, spec.TTY); derr != nil && ctx.Err() != nil {
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
		Detail:   "docker exec",
	}, nil
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
		MemoryBytes: int64(sample.MemoryStats.Usage),
	}
}

// statsSample is the minimal slice of docker's stats JSON the usage snapshot reads.
type statsSample struct {
	MemoryStats struct {
		Usage uint64 `json:"usage"`
	} `json:"memory_stats"`
}

// runDriver is the docker RunDriver: it inspects the exec for its terminal status and
// replays the buffered output for Logs.
type runDriver struct {
	client dockerClient
	execID string
	tty    bool
	buffer []byte
}

// Static assertion: *runDriver satisfies workspaceprovider.RunDriver.
var _ workspaceprovider.RunDriver = (*runDriver)(nil)

// Status reports the workload's phase. The first call (after the attach drained to EOF, i.e.
// the exec finished) inspects the real exit code and returns the terminal phase; ok=false.
func (r *runDriver) Status(ctx context.Context) (workspaceprovider.RunStatus, bool) {
	inspect, err := r.client.ContainerExecInspect(ctx, r.execID)
	if err != nil {
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunFailed, Detail: "exec inspect failed"}, false
	}
	if inspect.Running {
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, true
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

// Logs replays the workload's combined output buffered at attach time, from the cursor.
func (r *runDriver) Logs(_ context.Context, from workspaceprovider.LogCursor) (io.ReadCloser, error) {
	start := int(from)
	if start < 0 || start > len(r.buffer) {
		start = len(r.buffer)
	}
	return io.NopCloser(bytes.NewReader(r.buffer[start:])), nil
}

// drainHijack reads the attached exec's multiplexed output into a buffer (so Run.Logs can
// replay it from a cursor). It demuxes the docker stream framing unless a TTY (raw) was
// requested.
func drainHijack(attach types.HijackedResponse, tty bool) []byte {
	defer attach.Close()
	var combined bytes.Buffer
	// A demux error here means the stream closed early; the buffered prefix is still the
	// workload's real output and rides Run.Logs (the exit code rides Run.Status).
	_ = demux(attach.Reader, &combined, &combined, tty) //nolint:errcheck // partial output is still valid; the exit code is the authority.
	return combined.Bytes()
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
