/* Wildlife Watch motor-controller logic prototype.
 * DRY RUN ONLY: no motor pins are driven. See firmware/README.md.
 * 115200 baud, newline terminated: V1,1,ARM then V1,2,SLOW etc.
 */
#include <Arduino.h>
#include <stdio.h>
#include "Controller.h"
#include "DryRunMotorDriver.h"

wildlife::Controller controller;
wildlife::DryRunMotorDriver motors;

void setup() {
  motors.begin();
  motors.apply(controller.intent());
  Serial.begin(wildlife::SERIAL_BAUD);
  // No while(!Serial): motor servicing must not depend on a connected terminal.
}

void loop() {
  controller.tick(static_cast<uint32_t>(millis()));
  motors.apply(controller.intent());

  // Bound receive work so a noisy sender cannot starve the watchdog.
  for (uint8_t n = 0; n < 32 && Serial.available() > 0; ++n) {
    controller.feed(static_cast<char>(Serial.read()), static_cast<uint32_t>(millis()));
    motors.apply(controller.intent());
  }
  controller.tick(static_cast<uint32_t>(millis()));
  motors.apply(controller.intent());

  // Best-effort latest status; never block motor servicing on a full TX buffer.
  // A flood may coalesce statuses. This is not one ACK per incoming message.
  if (controller.dirty) {
    char status[64];
    const int length = snprintf(status, sizeof(status), "V1,%lu,%s,%s,%u,SIM\n",
        static_cast<unsigned long>(controller.lastSequence), controller.stateName(),
        controller.reason, static_cast<unsigned>(motors.last.duty[0]));
    if (length > 0 && length < static_cast<int>(sizeof(status)) &&
        Serial.availableForWrite() >= length) {
      Serial.write(reinterpret_cast<const uint8_t*>(status), static_cast<size_t>(length));
      controller.dirty = false;
    }
  }
}
