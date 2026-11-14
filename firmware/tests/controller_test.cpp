#include <cassert>
#include <iostream>
#include <string>
#include "../WildlifeMotorController/Controller.h"
using namespace wildlife;

void send(Controller& c, const std::string& text, uint32_t now) {
  for (char b : text) c.feed(b, now);
}
void armAndDrive(Controller& c, uint32_t now = 0) {
  send(c, "V1,1,ARM\nV1,2,CRUISE\n", now);
  assert(c.state == State::CRUISE);
}

int main() {
  {
    Controller c;
    send(c, "V1,1,SPEED,25\n", 0);
    assert(c.state == State::DISARMED);
    send(c, "V1,2,ARM\nV1,3,SPEED,25\n", 0);
    assert(c.state == State::DRIVE);
    for (auto duty : c.intent().duty) assert(duty == 64);
    send(c, "V1,4,SPEED,100\n", 100);
    for (auto duty : c.intent().duty) assert(duty == 255);
    c.tick(599); assert(c.state == State::DRIVE);
    send(c, "V1,5,SPEED,50\n", 600);
    assert(c.state == State::FAULT_LATCHED);
    send(c, "V1,6,DISARM\nV1,7,ARM\nV1,8,SPEED,1\n", 601);
    for (auto duty : c.intent().duty) assert(duty == 3);
    send(c, "V1,9,SPEED,0\nV1,10,SPEED,25\n", 602);
    assert(c.state == State::BRAKE_LATCHED);
    assert(c.intent().mode == OutputMode::BRAKE_REQUEST);
  }
  for (const auto* value : {"", "101", "-1", "+1", "1.0", "1,2", "1000", " 1"}) {
    Controller c; armAndDrive(c);
    send(c, std::string("V1,3,SPEED,") + value + "\n", 100);
    assert(c.state == State::FAULT_LATCHED);
    assert(c.lastSequence == 2);
  }
  {
    Controller c;
    assert(c.intent().mode == OutputMode::DISABLED);
    send(c, "V1,1,CRUISE\n", 0);
    assert(c.state == State::DISARMED);
    send(c, "V1,2,ARM\nV1,3,SLOW\n", 0);
    assert(c.state == State::SLOW);
    for (auto duty : c.intent().duty) assert(duty == SLOW_DUTY);
    send(c, "V1,4,BRAKE\nV1,5,CRUISE\n", 10);
    assert(c.state == State::BRAKE_LATCHED);
    assert(c.intent().mode == OutputMode::BRAKE_REQUEST);
    send(c, "V1,6,ARM\n", 20);
    assert(c.state == State::FAULT_LATCHED);
    send(c, "V1,7,DISARM\nV1,8,ARM\nV1,9,CRUISE\n", 30);
    assert(c.state == State::CRUISE);
  }
  {
    Controller c; armAndDrive(c);
    c.tick(499); assert(c.state == State::CRUISE);
    // A new command at the deadline must not revive motion.
    send(c, "V1,3,CRUISE\n", 500);
    assert(c.state == State::FAULT_LATCHED);
    assert(c.intent().mode == OutputMode::BRAKE_REQUEST);
  }
  {
    Controller c; armAndDrive(c, UINT32_MAX - 100);
    c.tick(398); assert(c.state == State::CRUISE);
    c.tick(399); assert(c.state == State::FAULT_LATCHED);
  }
  {
    Controller c; armAndDrive(c);
    send(c, "V1,2,SLOW\n", 100);
    assert(c.state == State::FAULT_LATCHED);
    assert(c.lastSequence == 2);
  }
  for (const auto* invalid : {"V1,3,FAST\n", "V2,3,SLOW\n", "V1,-1,SLOW\n",
       "V1,4294967296,SLOW\n", "V1,0,SLOW\n", "V1,3,SLOW,EXTRA\n", "V1,3,SLO\rW\n"}) {
    Controller c; armAndDrive(c);
    send(c, invalid, 100);
    assert(c.state == State::FAULT_LATCHED);
    assert(c.lastSequence == 2);
  }
  {
    Controller c; armAndDrive(c);
    send(c, std::string(60, 'x') + "V1,3,DISARM\n", 100);
    assert(c.state == State::FAULT_LATCHED);  // suffix must not execute
    send(c, "V1,3,DISARM\r\n", 110);
    assert(c.state == State::DISARMED);
  }
  {
    Controller c; armAndDrive(c);
    send(c, "V1,3,SL", 100);
    send(c, "OW\r\n", 200);
    assert(c.state == State::SLOW);
    send(c, "\n\r\nV1,4,", 300);
    c.tick(700); assert(c.state == State::FAULT_LATCHED);
  }
  {
    Controller c; armAndDrive(c);
    send(c, std::string("V1,3,SL\0OW\n", 11), 100);
    assert(c.state == State::FAULT_LATCHED);
  }
  {
    Controller c;
    send(c, "V1,4294967295,ARM\nV1,1,CRUISE\n", 0);
    assert(c.state == State::FAULT_LATCHED);
  }
  {
    Controller c; armAndDrive(c);
    send(c, "V1,3,FAULT\nV1,4,SLOW\n", 10);
    assert(c.state == State::FAULT_LATCHED);
    for (auto duty : c.intent().duty) assert(duty == 0);
  }
  std::cout << "PASS: arm, 4-motor intent, stop latch, timeout, rollover, parser, replay, and recovery\n";
}
