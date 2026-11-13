#pragma once
#include "Controller.h"

namespace wildlife {
// Deliberately has no pinMode, digitalWrite, or analogWrite calls.
// Replace with a reviewed, driver-specific backend after hardware identification.
class DryRunMotorDriver {
 public:
  MotorIntent last = {OutputMode::DISABLED, {0, 0, 0, 0}};
  void begin() {}
  void apply(const MotorIntent& request) { last = request; }
};
}
