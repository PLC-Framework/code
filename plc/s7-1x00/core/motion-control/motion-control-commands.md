# Motion Control Commands v9.0 Help

## Homing modes

| Value | Mode | Action |
| ----- | ---- | ------ |
| 0 | Direct homing (abs) | The current position of the technology object is set to the value of parameter "Position". |
| 1 | Direct homing (rel) | The current position of the technology object is shifted by the value of parameter "Position". |
| 2 |Passive homing (without reset) | Function same as "Mode" = 8 with the difference that the "homed" status is not reset when the function is enabled. |
| 3 | Active homing | The positioning axis/synchronous axis technology object performs a homing movement according to the configuration. After the completion of the motion, the axis is positioned at the value of the "Position" parameter. |
| 4 | Reserved | |
| 5 | Active homing(position parameter has no effect) | The positioning axis/synchronous axis technology object performs a homing movement according to the configuration. After completion of the motion, the axis is positioned at the home position configured under "Technology object > Configuration > Extended parameters > Homing > Active homing". (`<TO>.Homing.HomePosition`) |
| 6 | Absolute encoder adjustment(Relative) | The current position is shifted by the value of parameter "Position". The calculated absolute value offset is stored retentively in the CPU. (`<TO>.StatusSensor[1..4].AbsEncoderOffset`) |
| 7 | Absolute encoder adjustment (absolute) | The current position is set to the value of parameter "Position". The calculated absolute value offset is stored retentively in the CPU. (`<TO>.StatusSensor[1..4].AbsEncoderOffset`) |
| 8 | Passive homing | When the homing mark is detected, the actual value is set to the value of the "Position" parameter. |



## Command aborter

**MC_Home(mode= 2|8|10)** is aborted when:
│
├─ MC_Home(mode= 3|5|9)
└─ MC_Stop

**MC_Home(mode= 3|5)**,
**MC_Halt(mode = 1)**,
**MC_MoveRelative(bufferMode=0|1, active)**,
**MC_Move­Absolute(bufferMode=0|1, active)**,
**MC_Move­Velocity**,
**MC_MoveJog** are aborted when:
│
├─ **MC_Home(mode= 3|5)**
├─ **MC_Halt(mode= 0|1)**
├─ **MC_MoveAbsolute**
├─ **MC_MoveRelative(bufferMode=0, active)**
├─ **MC_MoveVelocity(bufferMode=0, active)**
├─ **MC_MoveJog**
├─ MC_MotionInVelocity
├─ MC_MotionInPosition
├─ MC_GearIn
├─ MC_GearInVelocity
├─ MC_GearInPos(active), MC_CamIn(active): *The status "Busy" = TRUE, "StartSync" or "InSync" = TRUE corresponds to an active synchronous operation.*
└─ **MC_Stop**

**MC_Move­Absolute(bufferMode=1, waiting)**,
**MC_Move­Relative(bufferMode=1, waiting)** are aborted when:
│
├─ **MC_Home(mode= 3|5)**
├─ **MC_Halt(mode= 0|1)**
├─ **MC_MoveAbsolute**
├─ **MC_MoveRelative(bufferMode=0, active)**
├─ **MC_MoveVelocity(bufferMode=0, active)**
├─ **MC_MoveJog**
├─ MC_MotionInVelocity
├─ MC_MotionInPosition
├─ MC_GearIn
├─ MC_GearInVelocity
├─ MC_GearInPos(active), MC_CamIn(active): *The status "Busy" = TRUE, "StartSync" or "InSync" = TRUE corresponds to an active synchronous operation.*
├─ MC_GearInPos(waiting), MC_CamIn(waiting): *The running job is aborted with "CommandAborted" = TRUE.*
└─ **MC_Stop**

**MC_Halt(mode= 0)** is aborted when:
│
├─ **MC_Home(mode= 3|5)**
├─ **MC_Halt(mode= 0)**
├─ **MC_MoveAbsolute**
├─ **MC_MoveRelative(bufferMode=0, active)**
├─ **MC_MoveVelocity(bufferMode=0, active)**
├─ **MC_MoveJog**
├─ MC_MotionInVelocity
├─ MC_MotionInPosition
├─ MC_GearIn
├─ MC_GearInVelocity
├─ MC_GearInPos(active), MC_CamIn(active): *The status "Busy" = TRUE, "StartSync" or "InSync" = TRUE corresponds to an active synchronous operation.*
└─ **MC_Stop**

**MC_Stop** is aborted when:
│
└─ **MC_Stop**: *`MC_Stop` job is aborted by another `MC_Stop` job with a stop response that is the same or higher.*