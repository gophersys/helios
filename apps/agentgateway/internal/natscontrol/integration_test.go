//go:build integration

// Package natscontrol_test's integration arm proves the control publisher over a REAL embedded
// nats-server (never a mock): a published agentruntime.ControlMessage reaches a real subscriber on
// agent.<id>.control with its verb/text/By intact.
package natscontrol_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	natsserver "github.com/nats-io/nats-server/v2/server"
	natsservertest "github.com/nats-io/nats-server/v2/test"
	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"

	"github.com/gophersys/eden/apps/agentgateway/internal/natscontrol"
)

// TestIntegration_PublishControl_RoundTrip proves a published control verb reaches a real subscriber.
func TestIntegration_PublishControl_RoundTrip(t *testing.T) {
	t.Parallel()
	url := startServer(t)
	conn, err := nats.Connect(url, nats.Timeout(5*time.Second))
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	t.Cleanup(conn.Close)

	const agentID agentruntime.AgentID = "agent-control-1"
	subscription, err := conn.SubscribeSync(agentruntime.ControlSubject(agentID))
	if err != nil {
		t.Fatalf("subscribe: %v", err)
	}
	t.Cleanup(func() { _ = subscription.Unsubscribe() }) //nolint:errcheck // best-effort reap.
	_ = conn.Flush()                                     //nolint:errcheck // propagate interest.

	adapter, err := natscontrol.New(conn)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	message := agentruntime.ControlMessage{AgentID: agentID, Verb: agentruntime.VerbSteer, Text: "hint", By: "user-x"}
	if pubErr := adapter.PublishControl(ctx, message); pubErr != nil {
		t.Fatalf("PublishControl: %v", pubErr)
	}

	received, err := subscription.NextMsg(5 * time.Second)
	if err != nil {
		t.Fatalf("no control message received: %v", err)
	}
	var decoded agentruntime.ControlMessage
	if decodeErr := json.Unmarshal(received.Data, &decoded); decodeErr != nil {
		t.Fatalf("decode: %v", decodeErr)
	}
	if decoded.AgentID != agentID || decoded.Verb != agentruntime.VerbSteer || decoded.Text != "hint" || decoded.By != "user-x" {
		t.Errorf("received = %+v, want {agent-control-1 steer hint user-x}", decoded)
	}
}

func startServer(t *testing.T) string {
	t.Helper()
	options := &natsserver.Options{Host: "127.0.0.1", Port: -1, NoLog: true, NoSigs: true}
	server := natsservertest.RunServer(options)
	t.Cleanup(server.Shutdown)
	if !server.ReadyForConnections(10 * time.Second) {
		t.Fatal("embedded nats-server not ready within 10s")
	}
	return server.ClientURL()
}
