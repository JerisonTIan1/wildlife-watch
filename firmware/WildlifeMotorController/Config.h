#pragma once
#include <stdint.h>

// This first build simulates motor intent. It NEVER configures motor pins.
// Do not bypass this gate until the actual H-bridge/board wiring is implemented.
#define WILDLIFE_DRY_RUN 1
#if WILDLIFE_DRY_RUN != 1
#error "Live motor backend not implemented. Identify board, driver, and motor ratings first."
#endif

namespace wildlife {
constexpr uint32_t SERIAL_BAUD = 115200;
constexpr uint32_t COMMAND_TIMEOUT_MS = 500;
constexpr uint8_t MOTOR_COUNT = 4;
// Illustrative 0..255 duty requests, NOT measured speeds or approved live values.
constexpr uint8_t CRUISE_DUTY = 120;
constexpr uint8_t SLOW_DUTY = 65;
constexpr uint8_t MAX_LINE_LENGTH = 47;  // excludes newline
static_assert(SLOW_DUTY < CRUISE_DUTY, "Slow must be below cruise");
}
