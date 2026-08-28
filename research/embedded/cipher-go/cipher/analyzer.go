package cipher

import (
	"fmt"
	"log"
	"net"
	"sync/atomic"
	"time"
)

/*-----------------------------------------------------------------------------------------------------
 *                                                                                             Analyzer
 *---------------------------------------------------------------------------------------------------*/

// Direction of a captured packet.
type Direction int

const (
	DirectionTX Direction = iota
	DirectionRX
)

func (d Direction) String() string {
	if d == DirectionTX {
		return "tx"
	}
	return "rx"
}

// Analyzer is the Go twin of the ck_analyzer module: decoded packet lines on
// the log, plus optional JSON events over UDP to the same collector, using
// the same schema as the firmware's net backend. A nil *Analyzer is valid
// and disables everything (mirroring the Kconfig-off state).
type Analyzer struct {
	LogPackets bool
	collector  net.Conn
	sequence   atomic.Uint32
	started    time.Time
}

// NewAnalyzer builds an analyzer. collectorAddress may be empty ("log only").
func NewAnalyzer(logPackets bool, collectorAddress string) (*Analyzer, error) {
	analyzer := &Analyzer{LogPackets: logPackets, started: time.Now()}

	if collectorAddress != "" {
		connection, err := net.Dial("udp", collectorAddress)
		if err != nil {
			return nil, fmt.Errorf("analyzer: collector dial: %w", err)
		}
		analyzer.collector = connection
	}

	return analyzer, nil
}

// CipherPacket records one encoded/decoded cipher header.
func (a *Analyzer) CipherPacket(direction Direction, header Header) {
	if a == nil {
		return
	}

	if a.LogPackets {
		log.Printf("ck_ana: cipher %s %s",
			map[Direction]string{DirectionTX: "TX", DirectionRX: "RX"}[direction], header)
	}

	if a.collector != nil {
		event := fmt.Sprintf(
			`{"seq":%d,"t":%d,"layer":"cipher","dir":"%s","src":%d,"dst":%d,"svc":%d,"op":%d,"type":%d,"len":%d,"flags":%d,"hops":%d}`,
			a.sequence.Add(1)-1, time.Since(a.started).Milliseconds(), direction,
			header.SourceID, header.DestinationID, header.ServiceID, header.OperationID,
			uint8(header.Type), header.PayloadLength, header.Flags, header.HopCount)
		_, _ = a.collector.Write([]byte(event)) // fire and forget, like the firmware
	}
}

// IfaceEvent records a transport event (connect/accept/close/error).
func (a *Analyzer) IfaceEvent(event string, detail int32) {
	if a == nil {
		return
	}

	if a.LogPackets {
		log.Printf("ck_ana: iface event=%s detail=%d", event, detail)
	}

	if a.collector != nil {
		line := fmt.Sprintf(`{"seq":%d,"t":%d,"layer":"iface","event":"%s","detail":%d}`,
			a.sequence.Add(1)-1, time.Since(a.started).Milliseconds(), event, detail)
		_, _ = a.collector.Write([]byte(line))
	}
}
