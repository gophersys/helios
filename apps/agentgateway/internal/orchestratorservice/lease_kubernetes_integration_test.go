//go:build integration

package orchestratorservice_test

import (
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/clientcmd"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// TestIntegrationKubernetes_LeaseElectsAndHandsOff proves the leader election the HA Deployment
// rests on, on a REAL k3d apiserver — the arm no test drove before this (the H6 hazard: a
// leaderelection nothing ever Starts is a latent split-brain the day it is first wired). Two
// KubernetesLease instances with DISTINCT holder identities contend for ONE coordination.k8s.io/v1
// Lease object:
//
//  1. replica-a starts its election alone → it ACQUIRES (IsLeader flips true).
//  2. replica-b starts against the same Lease → it stays FOLLOWER while a leads (and the
//     at-most-one-leader invariant holds at every observation).
//  3. replica-a's election is CANCELED (the graceful-shutdown path; ReleaseOnCancel releases the
//     Lease) → replica-b acquires within the election window — the HANDOFF the replicas:3
//     Deployment depends on, and the transition superviseLeadership promotes on.
//
// Short election cadence keeps the whole proof inside the integration lane's patience; the
// defaults only stretch the same mechanics. SKIPS when k3d/docker is unavailable locally; the
// devcontainer/CI substrate has both (FAIL-NOT-SKIP there per ADR-0020).
//
//nolint:paralleltest // serial by design: spins a real ephemeral k3d cluster; a parallel fan-out would stand up N clusters.
func TestIntegrationKubernetes_LeaseElectsAndHandsOff(t *testing.T) {
	kubeconfig, _ := bootK3dCluster(t)

	restConfig, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		t.Fatalf("build rest config from the k3d kubeconfig: %v", err)
	}
	clientset, err := kubernetes.NewForConfig(restConfig)
	if err != nil {
		t.Fatalf("build clientset: %v", err)
	}

	ctx := t.Context()
	const controlPlaneNamespace = "eden-lease-it"
	if _, err := clientset.CoreV1().Namespaces().Create(ctx, &corev1.Namespace{
		ObjectMeta: metav1.ObjectMeta{Name: controlPlaneNamespace},
	}, metav1.CreateOptions{}); err != nil {
		t.Fatalf("create the control-plane namespace: %v", err)
	}

	// The election cadence: short enough that acquire + handoff complete in seconds, long enough
	// that a renewal never flaps on a loaded runner (LeaseDuration > RenewDeadline > RetryPeriod*1.2).
	cadence := orchestratorservice.LeaseConfig{
		LeaseName:     "eden-orchestrator-it",
		Namespace:     controlPlaneNamespace,
		LeaseDuration: 3 * time.Second,
		RenewDeadline: 2 * time.Second,
		RetryPeriod:   500 * time.Millisecond,
	}
	dependencies := orchestratorservice.LeaseDependencies{
		Coordination: clientset.CoordinationV1(),
		Events:       clientset.CoreV1(),
	}

	replicaA := cadence
	replicaA.Identity = "replica-a"
	leaseA, err := orchestratorservice.NewKubernetesLease(replicaA, dependencies)
	if err != nil {
		t.Fatalf("NewKubernetesLease(replica-a): %v", err)
	}
	replicaB := cadence
	replicaB.Identity = "replica-b"
	leaseB, err := orchestratorservice.NewKubernetesLease(replicaB, dependencies)
	if err != nil {
		t.Fatalf("NewKubernetesLease(replica-b): %v", err)
	}

	// (1) replica-a elects alone → it acquires.
	cancelA := leaseA.Start(ctx)
	t.Cleanup(cancelA)
	waitLeadership(t, leaseA, true, 30*time.Second, "replica-a initial acquisition")

	// (2) replica-b contends → it stays follower while a leads; at most one leader at every look.
	cancelB := leaseB.Start(ctx)
	t.Cleanup(cancelB)
	for range 6 { // ~3s of observations across multiple election retry periods
		aLeads, aErr := leaseA.IsLeader(ctx)
		bLeads, bErr := leaseB.IsLeader(ctx)
		if aErr != nil || bErr != nil {
			t.Fatalf("IsLeader consult: aErr=%v bErr=%v", aErr, bErr)
		}
		if aLeads && bLeads {
			t.Fatal("BOTH replicas report leadership — the at-most-one-leader invariant is broken")
		}
		if bLeads {
			t.Fatal("replica-b acquired while replica-a still held an actively-renewed lease")
		}
		time.Sleep(500 * time.Millisecond)
	}

	// (3) cancel replica-a's election (the graceful shutdown; ReleaseOnCancel releases the Lease)
	// → replica-b MUST acquire within the election window: the handoff.
	cancelA()
	waitLeadership(t, leaseB, true, 30*time.Second, "replica-b handoff acquisition after replica-a released")
	waitLeadership(t, leaseA, false, 10*time.Second, "replica-a demotion after its election canceled")
}

// waitLeadership polls lease.IsLeader until it reports want, failing after deadline with the
// stage's name — the observation seam every arm of the election proof shares.
func waitLeadership(t *testing.T, lease *orchestratorservice.KubernetesLease, want bool, deadline time.Duration, stage string) {
	t.Helper()
	expire := time.Now().Add(deadline)
	for {
		got, err := lease.IsLeader(t.Context())
		if err != nil {
			t.Fatalf("%s: IsLeader consult: %v", stage, err)
		}
		if got == want {
			return
		}
		if time.Now().After(expire) {
			t.Fatalf("%s: IsLeader = %v, want %v after %s", stage, got, want, deadline)
		}
		time.Sleep(250 * time.Millisecond)
	}
}
