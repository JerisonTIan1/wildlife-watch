#pragma once
#include <stdint.h>
#include <string.h>
#include "Config.h"

namespace wildlife {
enum class State : uint8_t { DISARMED, ARMED, CRUISE, SLOW, BRAKE_LATCHED, FAULT_LATCHED };
enum class OutputMode : uint8_t { DISABLED, FORWARD, BRAKE_REQUEST };

struct MotorIntent {
  OutputMode mode;
  uint8_t duty[MOTOR_COUNT];
};

// Arduino-independent logic: tested on the host, then compiled into the sketch.
class Controller {
 public:
  State state = State::DISARMED;
  const char* reason = "BOOT";
  uint32_t lastSequence = 0;
  bool dirty = true;

  const char* stateName() const {
    switch (state) {
      case State::DISARMED: return "DISARMED";
      case State::ARMED: return "ARMED";
      case State::CRUISE: return "CRUISE";
      case State::SLOW: return "SLOW";
      case State::BRAKE_LATCHED: return "BRAKE_LATCHED";
      case State::FAULT_LATCHED: return "FAULT_LATCHED";
    }
    return "FAULT_LATCHED";
  }

  MotorIntent intent() const {
    MotorIntent out = {OutputMode::DISABLED, {0, 0, 0, 0}};
    if (state == State::CRUISE || state == State::SLOW) {
      out.mode = OutputMode::FORWARD;
      for (uint8_t i = 0; i < MOTOR_COUNT; ++i)
        out.duty[i] = state == State::CRUISE ? CRUISE_DUTY : SLOW_DUTY;
    } else if (state == State::BRAKE_LATCHED || state == State::FAULT_LATCHED) {
      // Brake is an explicit intent, NEVER inferred from duty == 0.
      out.mode = OutputMode::BRAKE_REQUEST;
    }
    return out;
  }

  void tick(uint32_t now) {
    if (isArmed() && static_cast<uint32_t>(now - lastValidMs_) >= COMMAND_TIMEOUT_MS)
      fault("TIMEOUT");
  }

  void feed(char byte, uint32_t now) {
    // Check before processing a late command: it cannot revive a timed-out car.
    tick(now);
    if (byte == '\n') {
      if (discard_) {
        discard_ = false;
        used_ = 0;
        return;
      }
      if (used_ && line_[used_ - 1] == '\r') --used_;  // accept CRLF
      line_[used_] = '\0';
      if (used_) parse(now);  // blank lines do not renew the watchdog
      used_ = 0;
      return;
    }
    if (discard_) return;
    if (used_ >= MAX_LINE_LENGTH || (byte != '\r' && (byte < 32 || byte > 126))) {
      fault("BAD_LINE");
      used_ = 0;
      discard_ = true;  // discard whole damaged frame, never execute its suffix
      return;
    }
    line_[used_++] = byte;
  }

 private:
  char line_[MAX_LINE_LENGTH + 1] = {};
  uint8_t used_ = 0;
  bool discard_ = false;
  uint32_t lastValidMs_ = 0;

  bool isArmed() const {
    return state == State::ARMED || state == State::CRUISE || state == State::SLOW;
  }

  void set(State next, const char* why) {
    state = next;
    reason = why;
    dirty = true;
  }

  void fault(const char* why) { set(State::FAULT_LATCHED, why); }

  void parse(uint32_t now) {
    if (strncmp(line_, "V1,", 3) != 0) { fault("BAD_VERSION"); return; }
    char* p = line_ + 3;
    if (*p < '0' || *p > '9') { fault("BAD_SEQUENCE"); return; }
    uint32_t seq = 0;
    while (*p >= '0' && *p <= '9') {
      const uint8_t digit = static_cast<uint8_t>(*p++ - '0');
      if (seq > (UINT32_MAX - digit) / 10) { fault("BAD_SEQUENCE"); return; }
      seq = seq * 10 + digit;
    }
    if (*p++ != ',' || seq == 0) { fault("BAD_SEQUENCE"); return; }
    if (seq <= lastSequence) { fault("OLD_SEQUENCE"); return; }
    // Unknown commands cannot consume a sequence number or keep motion alive.
    const bool arm = strcmp(p, "ARM") == 0;
    const bool disarm = strcmp(p, "DISARM") == 0;
    const bool cruise = strcmp(p, "CRUISE") == 0;
    const bool slow = strcmp(p, "SLOW") == 0;
    const bool brake = strcmp(p, "BRAKE") == 0;
    const bool fail = strcmp(p, "FAULT") == 0;
    if (!(arm || disarm || cruise || slow || brake || fail)) {
      fault("BAD_COMMAND"); return;
    }
    lastSequence = seq;
    if (brake) { set(State::BRAKE_LATCHED, "COMMAND"); return; }
    if (fail) { fault("HOST_FAULT"); return; }
    if (disarm) { set(State::DISARMED, "OPERATOR"); return; }
    if (arm) {
      if (state != State::DISARMED) { fault("DISARM_FIRST"); return; }
      lastValidMs_ = now;
      set(State::ARMED, "OPERATOR");
      return;
    }
    if (!isArmed()) {
      // CRUISE/SLOW cannot release a stop latch.
      reason = "NOT_ARMED";
      dirty = true;
      return;
    }
    lastValidMs_ = now;
    set(cruise ? State::CRUISE : State::SLOW, "COMMAND");
  }
};
}
