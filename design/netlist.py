from __future__ import annotations

import os

PROJECT_NAME = "stepper_controller"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYMBOL_LIBRARY_PATHS = (
    os.path.join(_REPO_ROOT, "library"),
    "/usr/share/kicad/symbols",
)

LIBRARY_NAME = "StepperController"

PHASES = ("A", "B")

MOTOR_CONNECTOR_PINS = {"A1": 1, "A2": 2, "B1": 3, "B2": 4}

DRIVER_PINS = {
    "OB1": "1", "BRB": "2", "VS_B": "3", "OB2": "4", "ENN": "5",
    "GND_LOW": "6", "CPO": "7", "CPI": "8", "VCP": "9", "SPREAD": "10",
    "V5OUT": "11", "MS1_AD0": "12", "NC": "13", "MS2_AD1": "14",
    "DIAG": "15", "INDEX": "16", "CLK": "17", "PDN_UART": "18",
    "VCC_IO": "19", "STEP": "20", "VREF": "21", "GND_HIGH": "22",
    "DIR": "23", "STDBY": "24", "OA2": "25", "VS_A": "26", "BRA": "27",
    "OA1": "28", "EPAD": "29",
}

#: Driver pins tied to the reference so the mode they select is fixed at
#: power-up rather than left to an internal pull-down.
DRIVER_STRAPPED_LOW = ("SPREAD", "MS1_AD0", "MS2_AD1", "CLK", "STDBY", "NC")

DRIVER_UART_ADDRESS = 0

MCU_PINS = {
    "PB9": "1", "PC14": "2", "PC15": "3", "VDD": "4", "VSS": "5",
    "NRST": "6", "PA0": "7", "PA1": "8", "PA2": "9", "PA3": "10",
    "PA4": "11", "PA5": "12", "PA6": "13", "PA7": "14", "PB0": "15",
    "PB1": "16", "PB2": "17", "PA8": "18", "NC_PA9": "19", "PC6": "20",
    "NC_PA10": "21", "PA11": "22", "PA12": "23", "PA13": "24",
    "PA14": "25", "PA15": "26", "PB3": "27", "PB4": "28", "PB5": "29",
    "PB6": "30", "PB7": "31", "PB8": "32",
}

#: Controller pin -> net, and the peripheral each assignment relies on.
MCU_FUNCTION = {
    "PA0": ("STEP_IN_MCU", "EXTI0"),
    "PA1": ("DRV_ENN", "GPIO"),
    "PA2": ("HOST_TX_MCU", "USART2_TX"),
    "PA3": ("HOST_RX_MCU", "USART2_RX"),
    "PA4": ("VM_SENSE", "ADC_IN4"),
    "PA5": ("MCU_DIR", "GPIO"),
    "PA6": ("DRV_DIAG", "EXTI6"),
    "PA7": ("DIR_IN_MCU", "GPIO"),
    "PB0": ("STAT_LED_D", "GPIO"),
    "PB1": ("DRV_INDEX", "GPIO"),
    "PA8": ("MCU_STEP", "TIM1_CH1"),
    "PA13": ("SWDIO_MCU", "SWDIO"),
    "PA14": ("SWCLK_MCU", "SWCLK"),
    "PB6": ("UART_TX_MCU", "USART1_TX"),
    "PB7": ("DRV_UART", "USART1_RX"),
    "VDD": ("+3V3", "supply"),
    "VSS": ("GND", "supply"),
    "NRST": ("NRST", "reset"),
}

#: Package pins the two sources disagree about: the datasheet pinout calls
#: them PA9 and PA10, the symbol calls them NC. No design decision rests on
#: either reading.
MCU_CONTESTED_PINS = {
    "19": {"datasheet": "PA9", "symbol": "NC/PA9"},
    "21": {"datasheet": "PA10", "symbol": "NC/PA10"},
}

#: Pins the datasheet's injection-susceptibility table gives no negative
#: injection tolerance at all.
MCU_NO_NEGATIVE_INJECTION_PINS = {
    "8": "PA1", "12": "PA5", "16": "PB1", "17": "PB2", "24": "PA13",
    "32": "PB8",
}

#: Negative injection every other pin tolerates, from the same table.
MCU_NEGATIVE_INJECTION_MAX_A = 5.0e-3

#: What each connector is for. A field conductor is one an integrator wires
#: and may drive below the board reference; a service conductor is mated
#: only by a probe that shares this board's reference.
CONNECTOR_ROLE = {"J1": "field", "J2": "field", "J3": "field",
                  "J4": "service", "J5": "service"}

MCU_UNUSED_PINS = tuple(
    MCU_PINS[name] for name in MCU_PINS
    if name not in MCU_FUNCTION)

BUCK_PINS = {"GND": "1", "SW": "2", "VIN": "3", "FB": "4", "EN": "5",
             "CB": "6"}

PFET_SOURCE_PINS = ("1", "2", "3")
PFET_GATE_PIN = "4"
PFET_DRAIN_PINS = ("5", "6", "7", "8")


def _part(lib_id, footprint, value, mpn=None, manufacturer=None, lcsc=None,
          datasheet="", in_bom=True, on_board=True):
    return {"lib_id": lib_id, "footprint": footprint, "value": value,
            "mpn": mpn, "manufacturer": manufacturer, "lcsc": lcsc,
            "datasheet": datasheet, "in_bom": in_bom, "on_board": on_board}


RESISTOR_PARTS = {
    "100R": ("C22775", "0603WAF1000T5E"),
    "1k": ("C21190", "0603WAF1001T5E"),
    "4.7k": ("C23162", "0603WAF4701T5E"),
    "10k": ("C25804", "0603WAF1002T5E"),
    "12k": ("C22790", "0603WAF1202T5E"),
    "22k": ("C31850", "0603WAF2202T5E"),
    "100k": ("C25803", "0603WAF1003T5E"),
}

RESISTOR_VALUES = {
    1: "100k", 2: "100k", 3: "100k", 4: "22k", 5: "100k", 6: "22k",
    7: "100k", 8: "12k", 9: "1k", 10: "22k", 11: "100R", 12: "100R",
    13: "10k", 14: "4.7k", 15: "4.7k", 16: "100R", 17: "100R",
    18: "100R", 19: "100R", 20: "1k", 21: "1k", 22: "1k",
}

CAPACITOR_PARTS = {
    "100nF": ("C113803", "CC0603KRX7R0BB104", "YAGEO",
              "Capacitor_SMD:C_0603_1608Metric", "Device:C"),
    "22nF": ("C106222", "CC0603KRX7R9BB223", "YAGEO",
             "Capacitor_SMD:C_0603_1608Metric", "Device:C"),
    "2.2uF": ("C277470", "CC0805KKX7R8BB225", "YAGEO",
              "Capacitor_SMD:C_0805_2012Metric", "Device:C"),
    "10uF": ("C326595", "CC0805KKX7R7BB106", "YAGEO",
             "Capacitor_SMD:C_0805_2012Metric", "Device:C"),
    "4.7uF": ("C132170", "CC1206KKX7R9BB475", "YAGEO",
              "Capacitor_SMD:C_1206_3216Metric", "Device:C"),
    "100uF_HY": ("C3008515", "HHXC500ARA101MJA0G", "NCC",
                 "Capacitor_SMD:CP_Elec_10x10.5", "Device:C_Polarized"),
}

CAPACITOR_VALUES = {
    1: "100uF_HY", 2: "100uF_HY", 3: "4.7uF", 4: "4.7uF", 5: "100nF",
    6: "100nF", 7: "22nF", 8: "100nF", 9: "2.2uF", 10: "100nF",
    11: "100nF", 12: "4.7uF", 13: "100nF", 14: "100nF", 15: "10uF",
    16: "10uF", 17: "100nF", 18: "100nF", 19: "100nF", 20: "100uF_HY",
    21: "100uF_HY",
}

SENSE_RESISTOR_REFERENCES = {"A": "RS1", "B": "RS2"}
SENSE_RESISTANCE_OHM = 0.100

ESD_CLAMP_NETS = {
    "D2": "HOST_TX", "D3": "HOST_RX", "D4": "STEP_IN", "D5": "DIR_IN",
    "D6": "SWDIO", "D7": "SWCLK", "D8": "NRST", "D9": "CFG_UART",
}


def _parts():
    parts = {
        "U1": _part(
            "Driver_Motor:TMC2226-SA",
            "%s:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.75x6.2mm_SegmentedMask"
            % LIBRARY_NAME,
            "TMC2226-SA-T", "TMC2226-SA-T", "TRINAMIC Motion Control",
            "C705366"),
        "U2": _part(
            "MCU_ST_STM32G0:STM32G030K8Tx",
            "Package_QFP:LQFP-32_7x7mm_P0.8mm",
            "STM32G030K8T6", "STM32G030K8T6TR", "STMicroelectronics",
            "C724044"),
        "U3": _part(
            "%s:LMR51430" % LIBRARY_NAME,
            "Package_TO_SOT_SMD:SOT-23-6",
            "LMR51430YF", "LMR51430YFDDCR", "Texas Instruments",
            "C5219261"),
        "Q1": _part(
            "%s:Si9407BDY" % LIBRARY_NAME,
            "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
            "Si9407BDY", "Si9407BDY-T1-GE3", "Vishay Siliconix", "C141567"),
        "D1": _part(
            "%s:TVS_Unidirectional" % LIBRARY_NAME, "Diode_SMD:D_SMB",
            "SMBJ26A", "SMBJ26A", "Littelfuse", "C315992"),
        "L1": _part(
            "Device:L", "%s:L_Bourns_SRP4020TA" % LIBRARY_NAME,
            "22uH", "SRP4020TA-220M", "Bourns", "C1847949"),
        "J1": _part(
            "%s:ScrewTerminal_1x02" % LIBRARY_NAME,
            "%s:TerminalBlock_KF128-5.08_1x02_P5.08mm" % LIBRARY_NAME,
            "KF128-5.08-2P-AA", "KF128-5.08-2P-AA", "Cixi Kefa Elec",
            "C474952"),
        "J2": _part(
            "Connector_Generic:Conn_01x04",
            "Connector_JST:JST_VH_B4P-VH_1x04_P3.96mm_Vertical",
            "B4P-VH", "B4P-VH(LF)(SN)", "JST Sales America", "C160317"),
        "J3": _part(
            "Connector_Generic:Conn_01x05",
            "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
            "KH-2.54PH180-1X5P-L11.5", "KH-2.54PH180-1X5P-L11.5",
            "Shenzhen Kinghelm Elec", "C2932699"),
        "J4": _part(
            "Connector_Generic:Conn_01x05",
            "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
            "KH-2.54PH180-1X5P-L11.5", "KH-2.54PH180-1X5P-L11.5",
            "Shenzhen Kinghelm Elec", "C2932699"),
        "J5": _part(
            "Connector_Generic:Conn_01x03",
            "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
            "KH-2.54PH180-1X3P-L11.5", "KH-2.54PH180-1X3P-L11.5",
            "Shenzhen Kinghelm Elec", "C2932698"),
    }
    for reference in ESD_CLAMP_NETS:
        parts[reference] = _part(
            "%s:TPD1E10B06" % LIBRARY_NAME,
            "%s:TI_X1SON-2_1.0x0.6mm_P0.65mm" % LIBRARY_NAME,
            "TPD1E10B06", "TPD1E10B06DPYR", "Texas Instruments", "C48260")
    for reference in ("D10", "D11"):
        parts[reference] = _part(
            "Device:LED", "LED_SMD:LED_0603_1608Metric",
            "KT-0603R", "KT-0603R", "Hubei KENTO Elec", "C2286")
    for reference in SENSE_RESISTOR_REFERENCES.values():
        parts[reference] = _part(
            "Device:R", "Resistor_SMD:R_1206_3216Metric",
            "100mR", "HoLRTX1206-1W-100mR-1%", "Milliohm", "C5123673")
    for index, value in sorted(RESISTOR_VALUES.items()):
        lcsc, mpn = RESISTOR_PARTS[value]
        parts["R%d" % index] = _part(
            "Device:R", "Resistor_SMD:R_0603_1608Metric", value, mpn,
            "UNI-ROYAL(Uniroyal Elec)", lcsc)
    for index, key in sorted(CAPACITOR_VALUES.items()):
        lcsc, mpn, manufacturer, footprint, lib_id = CAPACITOR_PARTS[key]
        parts["C%d" % index] = _part(
            lib_id, footprint, key.split("_")[0], mpn, manufacturer, lcsc)
    for index in range(1, 14):
        parts["TP%d" % index] = _part(
            "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
            "TestPoint", in_bom=False)
    for index in range(1, 5):
        parts["H%d" % index] = _part(
            "Mechanical:MountingHole", "MountingHole:MountingHole_3.2mm_M3",
            "MountingHole_M3", in_bom=False)
    for index in range(1, 5):
        parts["#FLG%d" % index] = _part(
            "power:PWR_FLAG", "", "PWR_FLAG", in_bom=False, on_board=False)
    return parts


PARTS = _parts()


def _driver_pin(name):
    return "U1." + DRIVER_PINS[name]


def _mcu_pin(name):
    return "U2." + MCU_PINS[name]


def _mcu_net_pin(net):
    """The controller pin the function map puts this net on."""
    found = [name for name, (assigned, _) in MCU_FUNCTION.items()
             if assigned == net]
    if len(found) != 1:
        raise KeyError("%s is on %d controller pins" % (net, len(found)))
    return _mcu_pin(found[0])


def _buck_pin(name):
    return "U3." + BUCK_PINS[name]


def _nets():
    ground = [
        _driver_pin("GND_LOW"), _driver_pin("GND_HIGH"),
        _driver_pin("EPAD"), _mcu_net_pin("GND"), _buck_pin("GND"),
        "R2.2", "R4.2", "R6.2", "R8.2", "RS1.2", "RS2.2",
        "D1.2", "D10.1", "D11.1",
        "C1.2", "C2.2", "C3.2", "C4.2", "C5.2", "C6.2", "C9.2", "C10.2",
        "C11.2", "C12.2", "C13.2", "C15.2", "C16.2", "C17.2", "C18.2",
        "C19.2", "C20.2", "C21.2",
        "J1.2", "J3.1", "J4.1", "J5.1",
        "TP9.1", "TP10.1", "TP11.1", "TP12.1", "TP13.1", "#FLG4.1",
    ]
    for reference in ESD_CLAMP_NETS:
        ground.append("%s.2" % reference)
    for name in DRIVER_STRAPPED_LOW:
        ground.append(_driver_pin(name))

    supply_input = ["J1.1", "#FLG1.1"] + [
        "Q1.%s" % pin for pin in PFET_DRAIN_PINS]
    motor_rail = [
        _driver_pin("VS_A"), _driver_pin("VS_B"), _buck_pin("VIN"),
        "R1.2", "R3.1", "R7.1", "D1.1",
        "C1.1", "C2.1", "C3.1", "C4.1", "C5.1", "C6.1", "C8.2", "C12.1",
        "C13.1", "C20.1", "C21.1", "TP1.1", "#FLG2.1",
    ] + ["Q1.%s" % pin for pin in PFET_SOURCE_PINS]
    logic_rail = [
        "L1.2", _mcu_net_pin("+3V3"), _driver_pin("VCC_IO"), "R5.1", "R10.2",
        "R13.2", "R20.1", "C11.1", "C15.1", "C16.1", "C17.1",
        "J4.2", "TP2.1", "#FLG3.1",
    ]

    nets = {
        "GND": ground,
        "VM_IN": supply_input,
        "VM": motor_rail,
        "+3V3": logic_rail,
        "PFET_G": ["Q1.%s" % PFET_GATE_PIN, "R1.1", "R2.1"],
        "BUCK_EN": [_buck_pin("EN"), "R3.2", "R4.1"],
        "SW": [_buck_pin("SW"), "L1.1", "C14.2"],
        "BOOT": [_buck_pin("CB"), "C14.1"],
        "FB": [_buck_pin("FB"), "R5.2", "R6.1"],
        "VM_SENSE": [_mcu_net_pin("VM_SENSE"), "R7.2", "R8.1", "C19.1"],
        "V5OUT": [_driver_pin("V5OUT"), "C9.1"],
        "VCP": [_driver_pin("VCP"), "C8.1"],
        "CP_OUT": [_driver_pin("CPO"), "C7.1"],
        "CP_IN": [_driver_pin("CPI"), "C7.2"],
        "DRV_VREF": [_driver_pin("VREF"), "C10.1"],
        "PHASE_A1": [_driver_pin("OA1"),
                     "J2.%d" % MOTOR_CONNECTOR_PINS["A1"]],
        "PHASE_A2": [_driver_pin("OA2"),
                     "J2.%d" % MOTOR_CONNECTOR_PINS["A2"]],
        "PHASE_B1": [_driver_pin("OB1"),
                     "J2.%d" % MOTOR_CONNECTOR_PINS["B1"]],
        "PHASE_B2": [_driver_pin("OB2"),
                     "J2.%d" % MOTOR_CONNECTOR_PINS["B2"]],
        "SENSE_A": [_driver_pin("BRA"), "RS1.1", "TP7.1"],
        "SENSE_B": [_driver_pin("BRB"), "RS2.1", "TP8.1"],
        "DRV_ENN": [_driver_pin("ENN"), _mcu_net_pin("DRV_ENN"),
                    "R13.1", "TP5.1"],
        "DRV_DIAG": [_driver_pin("DIAG"), _mcu_net_pin("DRV_DIAG"), "TP6.1"],
        "DRV_INDEX": [_driver_pin("INDEX"), _mcu_net_pin("DRV_INDEX")],
        "DRV_STEP": [_driver_pin("STEP"), "R11.2", "TP3.1"],
        "DRV_DIR": [_driver_pin("DIR"), "R12.2", "TP4.1"],
        "MCU_STEP": [_mcu_net_pin("MCU_STEP"), "R11.1"],
        "MCU_DIR": [_mcu_net_pin("MCU_DIR"), "R12.1"],
        "DRV_UART": [_driver_pin("PDN_UART"), _mcu_net_pin("DRV_UART"), "R9.2",
                     "R10.1", "R22.2"],
        "CFG_UART": ["R22.1", "D9.1", "J5.2"],
        "UART_TX_MCU": [_mcu_net_pin("UART_TX_MCU"), "R9.1"],
        "HOST_TX_MCU": [_mcu_net_pin("HOST_TX_MCU"), "R16.1"],
        "HOST_TX": ["R16.2", "D2.1", "J3.3"],
        "HOST_RX_MCU": [_mcu_net_pin("HOST_RX_MCU"), "R17.2"],
        "HOST_RX": ["R17.1", "D3.1", "J3.2"],
        "STEP_IN": ["R14.1", "D4.1", "J3.4"],
        "STEP_IN_MCU": [_mcu_net_pin("STEP_IN_MCU"), "R14.2"],
        "DIR_IN": ["R15.1", "D5.1", "J3.5"],
        "DIR_IN_MCU": [_mcu_net_pin("DIR_IN_MCU"), "R15.2"],
        "SWDIO": ["R18.1", "D6.1", "J4.3"],
        "SWDIO_MCU": [_mcu_net_pin("SWDIO_MCU"), "R18.2"],
        "SWCLK": ["R19.1", "D7.1", "J4.4"],
        "SWCLK_MCU": [_mcu_net_pin("SWCLK_MCU"), "R19.2"],
        "NRST": [_mcu_net_pin("NRST"), "C18.1", "D8.1", "J4.5", "J5.3"],
        "PWR_LED_A": ["R20.2", "D10.2"],
        "STAT_LED_D": [_mcu_net_pin("STAT_LED_D"), "R21.1"],
        "STAT_LED_A": ["R21.2", "D11.2"],
    }
    return nets


NETS = _nets()

NO_CONNECT = tuple("U2.%s" % pin for pin in sorted(MCU_UNUSED_PINS, key=int))


#: Supply range the board is marked with and every rail claim is evaluated
#: over, at the board's own input terminal.
INPUT_SUPPLY = {"min_v": 12.0, "max_v": 24.0}

#: The highest steady input the board is required to survive undamaged,
#: taken from the input clamp's stand-off voltage.
INPUT_SURVIVAL_MAX_V = 26.0

#: The current the input path, the reverse-blocking device and the input
#: terminal are rated for. A design decision: the motor's mechanical output
#: is not bounded by anything the board can measure.
INPUT_CURRENT_RATING_A = 2.0

#: Supply-lead parasitics the hot-plug claim is evaluated against. Budgets
#: for the integrator's wiring, not measurements of it.
SUPPLY_LEAD_INDUCTANCE_H = 1.5e-6
SUPPLY_LEAD_RESISTANCE_OHM = 0.05

RAILS = {
    "VM_IN": dict(INPUT_SUPPLY),
    "VM": dict(INPUT_SUPPLY),
    "GND": {"min_v": 0.0, "max_v": 0.0},
}

POWER_NETS = tuple(RAILS) + ("+3V3", "V5OUT")

#: Phase current the board is required to deliver continuously, and the sine
#: peak that follows from it.
PHASE_CURRENT_RMS_A = 1.5
PHASE_CURRENT_PEAK_A = PHASE_CURRENT_RMS_A * (2.0 ** 0.5)

#: Current-scale settings the driver's own current formula is evaluated at.
CURRENT_SCALE_MAX = 31
CURRENT_SCALE_MIN = 0

#: Motor envelope the board is designed against. The brief names no motor,
#: so these are assumptions the design depends on and they stay revisable.
MOTOR_PHASE_RESISTANCE_MIN_OHM = 1.0
MOTOR_PHASE_INDUCTANCE_MAX_H = 10.0e-3
MOTOR_ROTOR_INERTIA_MAX_KGM2 = 82.0e-7
MOTOR_MAX_SPEED_RPS = 18.0

#: Logic-side current the regulator and its rail claims are sized for.
LOGIC_CURRENT_MAX_A = 0.060

#: The regulator's own reference and the divider it is programmed with.
LOGIC_RAIL_NOMINAL_V = 3.3

#: The highest ambient every component rating on this board is checked at.
AMBIENT_MAX_C = 40.0

#: The ambient the continuous full-current claim is made at. Lower than the
#: board's own maximum because the driver's dissipation at full current is
#: what sets it.
CONTINUOUS_RATING_AMBIENT_C = 25.0

#: The shunt's own temperature at full phase current. An assumption: no
#: thermal solve and no measurement establishes it.
SENSE_RESISTOR_TEMPERATURE_C = 100.0

#: How far the delivered phase current may sit from its setting.
SENSE_ACCURACY_BUDGET = 0.13

#: The share of that budget the sense conductor's own resistance may take.
#: The driver compares the voltage at its pin, so copper between the shunt
#: and that pin is added to the shunt by the comparator itself.
SENSE_INTERCONNECT_BUDGET = 0.05

#: The lowest chopper frequency the driver's own settings table gives at its
#: internal clock, which is the frequency the bulk ripple is rated against.
CHOPPER_FREQUENCY_MIN_HZ = 23.4e3

#: Headroom below the driver's absolute maximum that a stored-energy
#: transient must leave.
MOTOR_RAIL_TRANSIENT_MAX_V = 31.0

#: Capacitance on the motor rail that is counted as bulk. Ceramics are left
#: out: their value at the rail voltage is a DC-bias curve this board does
#: not have.
BULK_REFERENCES = ("C1", "C2", "C20", "C21")

#: The capacitors the chopper ripple is claimed against; the ceramics' share
#: is left out, so the claim is an upper bound on what these carry.
RIPPLE_REFERENCES = BULK_REFERENCES

#: Nets that must reach a probe with the board installed, from the brief's
#: bring-up requirement.
PROBE_REQUIRED_NETS = (
    "VM", "+3V3", "GND", "DRV_STEP", "DRV_DIR", "DRV_ENN", "DRV_DIAG",
    "SENSE_A", "SENSE_B")

#: How far a probe may be from a reference probe and still count as having a
#: local ground.
PROBE_LOCAL_GROUND_MAX_MM = 25.0

#: The exposed pad's via array: what the layout must produce and the rules
#: check. Placed on the mask dams, so no via lies under solder paste.
THERMAL_VIA_COUNT = 9
THERMAL_VIA_DRILL_MM = 0.3
THERMAL_VIA_PAD_MM = 0.6

#: Each sense resistor's reference end reaches the plane through its own
#: vias and shares copper with nothing else.
#: The conductor the controller drives through a series element, and the
#: element itself: a source termination at or above the conductor's own
#: impedance is what keeps the driver's input from ringing past its
#: hysteresis.
SOURCE_TERMINATED = {"DRV_STEP": "R11", "DRV_DIR": "R12"}

PHASE_CONDUCTOR_RISE_MAX_K = 20.0
PROBE_GROUND_REACH_MM = 12.0
VIA_PLATING_MIN_UM = 18.0
SENSE_RETURN_VIA_COUNT = 2

CONNECTOR_FUNCTION_NETS = {
    "J1": {"VM_IN": "VM_IN", "GND": "GND"},
    "J2": {"A1": "PHASE_A1", "A2": "PHASE_A2",
           "B1": "PHASE_B1", "B2": "PHASE_B2"},
    "J3": {"GND": "GND", "HOST_RX": "HOST_RX", "HOST_TX": "HOST_TX",
           "STEP_IN": "STEP_IN", "DIR_IN": "DIR_IN"},
    "J4": {"GND": "GND", "+3V3": "+3V3", "SWDIO": "SWDIO",
           "SWCLK": "SWCLK", "NRST": "NRST"},
    "J5": {"GND": "GND", "CFG_UART": "CFG_UART", "NRST": "NRST"},
}

#: A conductor that enters the board and needs no clamp of its own, with the
#: structure that already bounds it.
ESD_EXEMPT = {
    "GND": "the reference the clamps divert into",
    "+3V3": "a regulated rail with bulk capacitance behind the regulator",
    "VM_IN": "clamped by the input suppressor through the reverse-blocking "
             "device's body diode, which conducts in the direction a "
             "positive surge arrives",
    "PHASE_A1": "clamped both ways by the driver's own bridge body diodes, "
                "into the motor rail above and the reference below",
}
for _phase in ("PHASE_A2", "PHASE_B1", "PHASE_B2"):
    ESD_EXEMPT[_phase] = ESD_EXEMPT["PHASE_A1"]

#: The build this board is costed and supplied for.
PLANNED_BUILD_QUANTITY = 50

ASSEMBLY_POLICY = {
    "placement_sides": 1,
    "through_hole_soldered_parts": 5,
}

#: Driver candidates the selection was made from, and the two requirements
#: that decided it. Each figure is read from that device's own datasheet.
DRIVER_CANDIDATES = {
    "TMC2226-SA-T": {
        "document": "tmc2226_trinamic",
        "continuous_rms_current_a": 1.6,
        "external_sense_resistors": True,
        "quiet_chopper": True,
        "selected": True,
    },
    "TMC2209-LA-T": {
        "document": "tmc2209_trinamic",
        "continuous_rms_current_a": 1.4,
        "external_sense_resistors": True,
        "quiet_chopper": True,
        "selected": False,
    },
    "TMC2240ATJ+T": {
        "document": "tmc2240_trinamic",
        "continuous_rms_current_a": 2.1,
        "external_sense_resistors": False,
        "quiet_chopper": True,
        "selected": False,
    },
}


def entering_conductors():
    entering = {}
    for reference, functions in CONNECTOR_FUNCTION_NETS.items():
        for net in functions.values():
            entering.setdefault(net, []).append(reference)
    return {net: sorted(refs) for net, refs in entering.items()}


def pin_to_net():
    mapping = {}
    for net_name, pin_refs in NETS.items():
        for pin_ref in pin_refs:
            if pin_ref in mapping:
                raise ValueError(
                    "pin %s assigned to both %s and %s"
                    % (pin_ref, mapping[pin_ref], net_name))
            mapping[pin_ref] = net_name
    for pin_ref in NO_CONNECT:
        if pin_ref in mapping:
            raise ValueError(
                "pin %s is both no-connect and on net %s"
                % (pin_ref, mapping[pin_ref]))
    return mapping
