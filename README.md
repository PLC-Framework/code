<div align="center">

<img src="logo.svg" width="140" alt="PLC Framework logo" />

# PLC Framework

Structured collection of functions, structures, enumerations, data types and utilities ready to import into your S7 PLC projects.

[**Documentation**](https://docs.plcframework.com)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Core Structure](#core-structure)
- [Getting Started](#getting-started)
- [Versioning](#versioning)

---

## Overview

PLC Framework provides a structured collection of functions, structures, enumerations, data types and utilities ready to import into projects.

---

## Core Structure

| Module              | Description                                                                         |
| :------------------ | :----------------------------------------------------------------------------------- |
| **ADT**             | Abstract data types: queue, stack, priority queue                                    |
| **Alarm**           | Alarm bit monitoring, safety alarms, add-on integration                              |
| **Communication**   | TCP, data exchange, network adapter config, logging                                  |
| **Control**         | Conveyor technology, manual control, position/range monitoring utilities             |
| **Controller**      | Motor and pneumatic actuator control, hydraulic table                                |
| **Converter**       | Unit and type converters (real ↔ string, angles, bit fields)                        |
| **DAD**             | Device-specific drivers (IFM, Leuze, Pepperl+Fuchs, Sick, SMC)                        |
| **Datetime**        | Date/time arithmetic, timestamps, delta time, formatting                             |
| **Fieldbus**        | PROFINET device activation, diagnostics (LLDX, PNIO)                                 |
| **HMI**             | Physical buttons, coded light signals, acoustic signals, screen selection            |
| **Maths**           | General mathematical utilities                                                       |
| **Motion Control**  | Technology objects, axis positioning, motion profile calculations                    |
| **Node**            | Node link UDTs for structured inter-block communication                              |
| **Protection**      | Power supply monitoring (Siemens SITOP PSE200U)                                      |
| **Safety**          | UF safety status blocks (enkey, FDI, feedback, RxDI, safety scanner, SendDP/RcvDP)    |
| **Scaling**         | Linear interpolation                                                                 |
| **String**          | String utilities: fill/remove spaces, character generation, numeric extraction       |
| **System**          | Background OB utilities, ESC routines                                                |
| **Util**            | Edge detection, bit toggle, limited counters                                         |

---

## Getting Started

Full documentation, development instructions and usage examples are available at:

**[docs.plcframework.com](https://docs.plcframework.com)**

---

## Versioning

This project follows a `vMajor.Minor` scheme:

| Change type                    | Major | Minor       |
| :------------------------------ | :---: | :---------- |
| Bug fix                         |  —    | incremented |
| Patch                           |  —    | incremented |
| Backwards-compatible change     |  —    | incremented |
| Refactoring                     |  —    | incremented |
| New feature                     |  —    | incremented |
| Feature removal                 | incremented | reset to 0 |
| Breaking change                 | incremented | reset to 0 |
