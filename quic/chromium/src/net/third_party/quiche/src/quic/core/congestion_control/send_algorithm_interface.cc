// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "net/third_party/quiche/src/quic/core/congestion_control/send_algorithm_interface.h"

#include "net/abrcc/cc/cc_wrapper.h"
#include "net/abrcc/cc/cc_selector.h"
#include "net/abrcc/cc/bbr_adapter.h"
#include "net/abrcc/cc/target.h"
#include "net/abrcc/cc/gap.h"
#include "net/abrcc/cc/minerva.h"

#include "net/third_party/quiche/src/quic/core/congestion_control/bbr_sender.h"
#include "net/third_party/quiche/src/quic/core/congestion_control/tcp_cubic_sender_bytes.h"
#include "net/third_party/quiche/src/quic/core/quic_packets.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_bbr2_sender.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_bug_tracker.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_fallthrough.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flag_utils.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_flags.h"
#include "net/third_party/quiche/src/quic/platform/api/quic_pcc_sender.h"

namespace quic {

class RttStats;

// Factory for send side congestion control algorithm.
SendAlgorithmInterface* SendAlgorithmInterface::Create(
    const QuicClock* clock,
    const RttStats* rtt_stats,
    const QuicUnackedPacketMap* unacked_packets,
    CongestionControlType congestion_control_type,
    QuicRandom* random,
    QuicConnectionStats* stats,
    QuicPacketCount initial_congestion_window) {
  QuicPacketCount max_congestion_window =
      GetQuicFlag(FLAGS_quic_max_congestion_window);
  congestion_control_type = kBBR;
  
  auto *selector = CCSelector::GetInstance();
  congestion_control_type = selector->getCongestionControlType();
  
  QUIC_LOG(WARNING) << "CC " << congestion_control_type;
  SendAlgorithmInterface* instance = nullptr;
  switch (congestion_control_type) {
    case kAbbr:
      QUIC_LOG(WARNING) << "Using Adapter BBR";
      instance = new BbrAdapter(clock->ApproximateNow(), rtt_stats, unacked_packets,
                           initial_congestion_window, max_congestion_window,
                           random, stats);
      break;
    case kTarget:
      QUIC_LOG(WARNING) << "Using Target CC";
      instance = new BbrTarget(clock->ApproximateNow(), rtt_stats, unacked_packets,
                           initial_congestion_window, max_congestion_window,
                           random, stats);
      break;
    case kGap:
      QUIC_LOG(WARNING) << "Using Gap CC";
      instance = new BbrGap(clock->ApproximateNow(), rtt_stats, unacked_packets,
                           initial_congestion_window, max_congestion_window,
                           random, stats);
      break;
    case kGoogCC:  
    case kBBR:
      QUIC_LOG(WARNING) << "Using BBR";
      instance = new BbrSender(clock->ApproximateNow(), rtt_stats, unacked_packets,
                           initial_congestion_window, max_congestion_window,
                           random, stats);
      break;
    case kBBRv2:
      QUIC_LOG(WARNING) << "Using BBRv2";
      instance = new QuicBbr2Sender(clock->ApproximateNow(), rtt_stats,
                                unacked_packets, initial_congestion_window,
                                max_congestion_window, random, stats);
      break;
    case kPCC:
      QUIC_LOG(WARNING) << "Using PCC";
      instance = CreatePccSender(clock, rtt_stats, unacked_packets, random, stats,
                               initial_congestion_window,
                               max_congestion_window);
      break;
    case kCubicBytes:
      QUIC_LOG(WARNING) << "Using Cubic";
      instance = new TcpCubicSenderBytes(
          clock, rtt_stats, false /* don't use Reno */,
          initial_congestion_window, max_congestion_window, stats);
      break;
    case kMinervaBytes:
      QUIC_LOG(WARNING) << "Using Minerva";
      instance = new TcpMinervaSenderBytes(
          rtt_stats, initial_congestion_window, max_congestion_window, stats);
      break;
    case kRenoBytes:
      QUIC_LOG(WARNING) << "Using Reno";
      instance = new TcpCubicSenderBytes(clock, rtt_stats, true /* use Reno */,
                                     initial_congestion_window,
                                     max_congestion_window, stats);
      break;
  }
  selector->setSendAlgorithmInterface(instance);
  return new CCWrapper(instance);
}

}  // namespace quic
