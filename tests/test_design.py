from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from design import (build, cost, evidence, geometry, ksym,  # noqa: E402
                    layout, libraries, manifest, models, netlist, orientation,
                    physical, rules, simulation, thermal)

TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402
from pcbqa.sim import model_registry, ngspice  # noqa: E402
from pcbqa.sim import scenario as sim_scenario  # noqa: E402


class DesignSource(unittest.TestCase):
    def test_pin_assignment_is_unique(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(len(mapping),
                         sum(len(pins) for pins in netlist.NETS.values()))

    def test_every_symbol_pin_is_connected_or_declared_no_connect(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        mapping = netlist.pin_to_net()
        declared = set(netlist.NO_CONNECT)
        unresolved = []
        for reference, part in netlist.PARTS.items():
            for number in library.pins(part["lib_id"]):
                pin_ref = "%s.%s" % (reference, number)
                if pin_ref not in mapping and pin_ref not in declared:
                    unresolved.append(pin_ref)
        self.assertEqual(unresolved, [])

    def test_declared_pins_exist_on_the_symbol(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        missing = []
        for pin_ref in list(netlist.pin_to_net()) + list(netlist.NO_CONNECT):
            reference, _, number = pin_ref.partition(".")
            lib_id = netlist.PARTS[reference]["lib_id"]
            if number not in library.pins(lib_id):
                missing.append(pin_ref)
        self.assertEqual(missing, [])

    def test_the_library_holds_nothing_the_design_source_does_not_write(self):
        produced = set(libraries.artifacts())
        present = set()
        for root, _, names in os.walk(libraries.FOOTPRINT_DIR):
            for name in names:
                present.add(os.path.join(root, name))
        present.add(libraries.SYMBOL_LIB_PATH)
        self.assertEqual(sorted(present - produced), [])

    def test_the_committed_design_files_are_the_generated_ones(self):
        with open(build.schematic_path(), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), build.generate_schematic_text())
        for path, text in libraries.artifacts().items():
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text, path)

    def test_the_committed_manifest_is_the_generated_one(self):
        with open(manifest.MANIFEST_PATH, "r", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), manifest.document())

    def test_the_controller_pin_map_and_the_netlist_agree(self):
        mapping = netlist.pin_to_net()
        for name, (net, _) in netlist.MCU_FUNCTION.items():
            self.assertEqual(mapping["U2." + netlist.MCU_PINS[name]], net)

    def test_the_contested_controller_pins_are_left_unconnected(self):
        for number in netlist.MCU_CONTESTED_PINS:
            self.assertIn("U2.%s" % number, netlist.NO_CONNECT)


class DriverContract(unittest.TestCase):
    def setUp(self):
        self.mapping = netlist.pin_to_net()
        self.parameters = rules.load_parameters()

    def test_the_driver_pin_numbers_match_the_symbol(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        pins = library.pins(netlist.PARTS["U1"]["lib_id"])
        self.assertEqual(sorted(netlist.DRIVER_PINS.values(), key=int),
                         sorted(pins, key=int))

    def test_every_strapped_mode_pin_sits_on_the_reference(self):
        for name in netlist.DRIVER_STRAPPED_LOW:
            self.assertEqual(
                self.mapping["U1." + netlist.DRIVER_PINS[name]], "GND")

    def test_the_enable_input_is_pulled_to_the_disabled_level(self):
        self.assertIn("R13.1", netlist.NETS["DRV_ENN"])
        self.assertIn("R13.2", netlist.NETS["+3V3"])

    def test_each_sense_resistor_reaches_one_bridge_return_and_the_reference(
            self):
        for phase, reference in netlist.SENSE_RESISTOR_REFERENCES.items():
            self.assertEqual(self.mapping["%s.1" % reference],
                             "SENSE_%s" % phase)
            self.assertEqual(self.mapping["%s.2" % reference], "GND")
            self.assertIn("U1." + netlist.DRIVER_PINS["BR%s" % phase],
                          netlist.NETS["SENSE_%s" % phase])

    def test_the_two_sense_conductors_share_no_component(self):
        left = {pin.split(".")[0] for pin in netlist.NETS["SENSE_A"]}
        right = {pin.split(".")[0] for pin in netlist.NETS["SENSE_B"]}
        self.assertEqual(left & right, {"U1"})

    def test_the_motor_connector_carries_one_phase_terminal_per_position(self):
        for function, pin in netlist.MOTOR_CONNECTOR_PINS.items():
            self.assertEqual(self.mapping["J2.%d" % pin], "PHASE_" + function)
            self.assertIn("U1." + netlist.DRIVER_PINS["O%s" % function],
                          netlist.NETS["PHASE_" + function])

    def test_the_configuration_line_carries_its_pull_up_and_series_element(
            self):
        self.assertIn("R10.1", netlist.NETS["DRV_UART"])
        self.assertIn("R9.2", netlist.NETS["DRV_UART"])
        self.assertIn("U1." + netlist.DRIVER_PINS["PDN_UART"],
                      netlist.NETS["DRV_UART"])


class Protection(unittest.TestCase):
    def setUp(self):
        self.mapping = netlist.pin_to_net()

    def test_the_blocking_device_faces_the_input(self):
        for pin in netlist.PFET_DRAIN_PINS:
            self.assertEqual(self.mapping["Q1.%s" % pin], "VM_IN")
        for pin in netlist.PFET_SOURCE_PINS:
            self.assertEqual(self.mapping["Q1.%s" % pin], "VM")

    def test_only_the_terminal_and_the_blocking_device_touch_the_input(self):
        owners = {pin.split(".")[0] for pin in netlist.NETS["VM_IN"]}
        self.assertEqual(owners - {"#FLG1"}, {"J1", "Q1"})

    def test_every_entering_conductor_is_clamped_or_exempt(self):
        clamped = set(netlist.ESD_CLAMP_NETS.values())
        for net in netlist.entering_conductors():
            self.assertTrue(net in clamped or net in netlist.ESD_EXEMPT, net)

    def test_no_field_conductor_reaches_a_zero_injection_pin(self):
        parameters = rules.load_parameters()
        for result in rules.evaluate_injection_policy(parameters):
            if result["id"] == "no_field_conductor_reaches_a_zero_injection_pin":
                self.assertEqual(result["measured"], 0)
                return
        self.fail("the injection policy produced no field-conductor claim")


class Layout(unittest.TestCase):
    def test_every_part_with_a_land_pattern_has_a_pose(self):
        placed = layout.fixed_placements()
        for reference, part in netlist.PARTS.items():
            if part["footprint"]:
                self.assertIn(reference, placed)

    def test_the_exposed_pad_via_field_clears_every_mask_window(self):
        self.assertGreaterEqual(
            len(libraries.thermal_via_positions_mm()),
            netlist.THERMAL_VIA_COUNT)
        self.assertGreaterEqual(
            libraries.thermal_via_to_mask_clearance_mm(), 0.15)
        self.assertGreaterEqual(libraries.paste_coverage_fraction(), 0.50)

    def test_the_stackup_names_one_role_for_every_copper_layer(self):
        self.assertEqual(len(build.LAYER_ROLES), build.COPPER_LAYERS)
        self.assertEqual(len(manifest.stackup_expected()), build.COPPER_LAYERS)

    def test_the_planes_are_the_nets_the_router_may_not_draw(self):
        from design import route
        for net in layout.PLANE_NETS:
            self.assertIn(net, route.RESERVED_NETS)

    def test_the_marking_states_what_the_board_claims(self):
        text = layout.rating_text()
        self.assertIn("%g" % netlist.INPUT_SUPPLY["min_v"], text)
        self.assertIn("%g" % netlist.INPUT_SUPPLY["max_v"], text)
        self.assertIn("%.1f" % netlist.PHASE_CURRENT_RMS_A, text)


class Evidence(unittest.TestCase):
    def test_every_document_is_present_and_unchanged(self):
        self.assertEqual(evidence.verify(), [])

    def test_the_committed_index_is_the_computed_one(self):
        self.assertEqual(evidence.load_index(), evidence.compute_index())

    def test_every_parameter_cites_a_frozen_document(self):
        recorded = set(evidence.load_index()["documents"])
        missing = []

        def walk(node, path):
            if isinstance(node, dict):
                document = node.get("document")
                if isinstance(document, str) and document not in recorded:
                    missing.append((path, document))
                for key, value in node.items():
                    walk(value, path + "." + key)

        walk(rules.load_parameters()["parts"], "parts")
        self.assertEqual(missing, [])

    def test_every_part_in_the_bom_has_a_catalogue_entry(self):
        catalog = rules.load_catalog()["parts"]
        for reference, part in netlist.PARTS.items():
            if part["in_bom"]:
                self.assertIn(part["lcsc"], catalog, reference)

    def test_catalogue_stock_covers_the_planned_build(self):
        limits = cost.stock_limited_boards()
        self.assertGreaterEqual(min(limits.values()),
                                netlist.PLANNED_BUILD_QUANTITY)


class Requirements(unittest.TestCase):
    def setUp(self):
        self.results = rules.evaluate_all()

    def test_no_requirement_fails(self):
        failed = [result["id"] for result in self.results
                  if result["verdict"]["result"] == claim.FAIL]
        self.assertEqual(failed, [])

    def test_every_unknown_names_what_would_establish_it(self):
        for result in self.results:
            if result["verdict"]["result"] != claim.UNKNOWN_RESULT:
                continue
            evidence_record = result["claim"]["evidence"]
            self.assertTrue(
                evidence_record["omitted_contributions"]
                or evidence_record["assumptions"], result["id"])

    def test_the_committed_report_is_the_generated_one(self):
        with open(rules.REPORT_PATH, "r", encoding="utf-8") as handle:
            committed = json.load(handle)
        self.assertEqual(committed["summary"], rules.summarise(self.results))

    def test_the_selected_driver_meets_every_selection_requirement(self):
        selected = [name for name, entry in netlist.DRIVER_CANDIDATES.items()
                    if entry["selected"]]
        self.assertEqual(len(selected), 1)
        entry = netlist.DRIVER_CANDIDATES[selected[0]]
        self.assertEqual(rules._driver_requirements_failed(entry), [])
        self.assertEqual(netlist.PARTS["U1"]["mpn"], selected[0])

    def test_every_rejected_driver_fails_a_stated_requirement(self):
        for name, entry in netlist.DRIVER_CANDIDATES.items():
            if entry["selected"]:
                continue
            self.assertTrue(rules._driver_requirements_failed(entry), name)


class Thermal(unittest.TestCase):
    def setUp(self):
        self.parameters = rules.load_parameters()

    def test_conduction_is_a_lower_bound_on_the_driver_dissipation(self):
        self.assertLess(thermal.driver_conduction_w(self.parameters),
                        thermal.driver_dissipation_w(self.parameters))

    def test_the_report_states_what_it_does_not_establish(self):
        document = thermal.document(self.parameters)
        self.assertTrue(document["not_established"])
        self.assertGreater(document["total_w"], 0.0)

    def test_the_committed_report_is_the_generated_one(self):
        with open(thermal.REPORT_PATH, "r", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle),
                             thermal.document(self.parameters))


class Simulation(unittest.TestCase):
    def setUp(self):
        records = list(models.records())
        records.extend(simulation.extracted_records())
        self.registry = model_registry.ModelRegistry(records)
        self.documents = simulation.documents()

    def test_every_scenario_validates(self):
        for name, document in self.documents.items():
            sim_scenario.validate_scenario(document)

    def test_the_committed_scenarios_are_the_generated_ones(self):
        for name, document in self.documents.items():
            with open(os.path.join(simulation.SIM_DIR, name),
                      encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), document, name)

    def test_the_committed_models_are_the_generated_ones(self):
        with open(models.MODELS_PATH, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), models.records())

    def test_every_scenario_runs_and_every_assertion_holds(self):
        workdir = os.path.join(REPO_ROOT, "out", "sim")
        for name, document in sorted(self.documents.items()):
            run = ngspice.run_scenario(self.registry, document,
                                       os.path.join(workdir, name))
            self.assertEqual(run["status"], "ran", name)
            for measurement, entry in (run["measurements"] or {}).items():
                verdict = entry.get("verdict")
                if verdict is None:
                    continue
                self.assertEqual(verdict["result"], claim.PASS,
                                 "%s: %s" % (name, measurement))

    def test_the_clamp_model_bounds_the_datasheet_limits(self):
        breakdown_v, test_a, series_ohm = models.fit(rules.load_parameters())
        tvs = rules._spec(rules.load_parameters(), "D1")["tvs"]
        self.assertEqual(breakdown_v, tvs["breakdown_max_v"]["value"])
        self.assertGreater(series_ohm, 0.0)
        clamping = breakdown_v + series_ohm * (
            tvs["clamping_current_a"]["value"] - test_a)
        self.assertAlmostEqual(clamping, tvs["clamping_v"]["value"], places=6)


class Fabrication(unittest.TestCase):
    def test_the_selection_matches_the_declared_requirements(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            requirements = json.load(handle)
        with open(os.path.join(REPO_ROOT, "fab", "selection.json"),
                  encoding="utf-8") as handle:
            selection = json.load(handle)
        self.assertTrue(selection["feasible"])
        self.assertEqual(selection["profile"]["copper_layers"],
                         requirements["copper_layers"])
        self.assertEqual(selection["profile"]["copper_layers"],
                         build.COPPER_LAYERS)

    def test_the_frozen_physical_inputs_still_match_the_catalog(self):
        self.assertEqual(physical.verify(), [])

    def test_the_extracted_paths_are_the_conductors_that_carry_the_claim(self):
        for alias, declared in simulation.extracted_paths().items():
            self.assertIn(declared["net"], ("SENSE_A", "SENSE_B"), alias)
            self.assertIn(declared["net"], netlist.NETS)

    def test_the_declared_floor_is_at_or_above_the_fabrication_request(self):
        with open(os.path.join(REPO_ROOT, "fab", "requirements.json"),
                  encoding="utf-8") as handle:
            requirements = json.load(handle)
        self.assertLessEqual(requirements["min_track_mm"],
                             build.DESIGN_RULES["min_track_width"])
        self.assertLessEqual(requirements["min_space_mm"],
                             build.DESIGN_RULES["min_clearance"])
        self.assertLessEqual(requirements["min_drill_mm"],
                             build.DESIGN_RULES["min_through_hole_diameter"])
        self.assertLessEqual(requirements["min_via_diameter_mm"],
                             build.DESIGN_RULES["min_via_diameter"])


class BoardGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = geometry.snapshot()

    def test_the_curve_reproduces_a_worked_current(self):
        # IPC-2221 external: 0.5 mm of 1 oz copper carries 1.6127 A at the
        # 10 K rise, worked from I = 0.048 * rise**0.44 * area_mil2**0.725.
        rise = geometry.temperature_rise_k(1.6127, 0.5 * 0.04064)
        self.assertAlmostEqual(rise, 10.0, places=2)

    def test_every_geometry_requirement_holds_on_the_routed_board(self):
        results = geometry.evaluate_all(rules.load_parameters())
        for result in results:
            self.assertEqual(claim.verdict(result["claim"])["result"],
                             claim.PASS, result["id"])

    def test_a_narrow_layer_change_is_reported(self):
        board = json.loads(json.dumps(self.board))
        for via in board["vias"]:
            if via["net"].startswith("PHASE_"):
                via["drill_mm"] = layout.VIA_DRILL_MM
        results = geometry.evaluate_layer_changes(None, board)
        self.assertGreater(results[0]["measured"], 0)

    def test_a_thin_conductor_is_reported(self):
        board = json.loads(json.dumps(self.board))
        for track in board["tracks"]:
            if track["net"] == "PHASE_A1":
                track["width_mm"] = 0.15
        results = geometry.evaluate_conductor_rise(None, board)
        thin = [result for result in results
                if result["identity"] == "PHASE_A1"]
        self.assertGreater(thin[0]["measured"],
                           netlist.PHASE_CONDUCTOR_RISE_MAX_K)
        self.assertNotEqual(claim.verdict(thin[0]["claim"])["result"],
                            claim.PASS)

    def test_a_shared_shunt_reference_is_reported(self):
        board = json.loads(json.dumps(self.board))
        one, other = sorted(netlist.SENSE_RESISTOR_REFERENCES.values())
        bridge = dict(board["tracks"][0])
        bridge.update({"net": "GND", "layer": "F.Cu", "width_mm": 0.2,
                       "start": board["pads"]["%s.2" % one]["at"],
                       "end": board["pads"]["%s.2" % other]["at"]})
        board["tracks"].append(bridge)
        results = geometry.evaluate_sense_returns(None, board)
        shared = [result for result in results
                  if result["id"].endswith("share_no_surface_conductor")]
        self.assertEqual(shared[0]["measured"], 1)

    def test_the_impedance_matches_a_worked_microstrip(self):
        # Hammerstad, w = 0.25 mm over 0.2104 mm of dk 4.4: e_eff 3.210,
        # w/h > 1, so Z0 = 376.730313668 / (sqrt(e_eff) * (u + 1.393 +
        # 0.667 * ln(u + 1.444))) = 65.16 ohm.
        impedance = geometry.microstrip_impedance_ohm(0.25, 0.2104, 4.4)
        self.assertAlmostEqual(impedance, 65.16, places=2)

    def test_a_narrower_conductor_presents_a_higher_impedance(self):
        self.assertGreater(geometry.microstrip_impedance_ohm(0.15, 0.2104,
                                                             4.4),
                           geometry.microstrip_impedance_ohm(0.25, 0.2104,
                                                             4.4))

    def test_a_critically_damped_loop_does_not_overshoot(self):
        self.assertEqual(geometry.overshoot_fraction(1.0), 0.0)
        self.assertGreater(geometry.overshoot_fraction(0.5), 0.0)
        self.assertLess(geometry.overshoot_fraction(0.9),
                        geometry.overshoot_fraction(0.5))

    def test_the_dielectric_comes_from_the_selected_stackup(self):
        dielectric = geometry.signal_dielectric()
        for record in dielectric.values():
            self.assertEqual(record["source_type"], "approved-evidence")
        with open(os.path.join(REPO_ROOT, "fab", "selection.json"),
                  encoding="utf-8") as handle:
            selection = json.load(handle)
        self.assertIn(selection["stackup"],
                      dielectric["height_mm"]["source"])

    def test_a_series_element_below_the_impedance_is_reported(self):
        board = json.loads(json.dumps(self.board))
        for track in board["tracks"]:
            if track["net"] in netlist.SOURCE_TERMINATED:
                track["width_mm"] = 0.05
        results = geometry.evaluate_source_termination(None, board)
        for result in results:
            self.assertGreater(
                result["measured"],
                result["claim"]["requirement"]["assertion"]["value"])
            self.assertNotEqual(claim.verdict(result["claim"])["result"],
                                claim.PASS)

    def test_every_probe_reference_distance_is_measured_on_the_board(self):
        results = geometry.evaluate_probe_reference(None, self.board)
        self.assertLessEqual(results[0]["measured"],
                             netlist.PROBE_GROUND_REACH_MM)


class Orientation(unittest.TestCase):
    """The library-zero offsets, and what would happen if they moved."""

    #: What the frozen evidence derives today. Pinned here so a change in
    #: the evidence or in the scorer has to be looked at rather than
    #: absorbed: every one of these turns a part on the board.
    EXPECTED_OFFSETS = {
        "C106222": 0.0,   "C113803": 0.0,   "C132170": 0.0,
        "C141567": 270.0, "C160317": 0.0,   "C1847949": 0.0,
        "C21190": 0.0,    "C22775": 0.0,    "C22790": 0.0,
        "C2286": 180.0,   "C23162": 0.0,    "C25803": 0.0,
        "C25804": 0.0,    "C277470": 0.0,   "C2932698": 270.0,
        "C2932699": 270.0, "C3008515": 0.0, "C315992": 0.0,
        "C31850": 0.0,    "C326595": 0.0,   "C474952": 0.0,
        "C48260": 0.0,    "C5123673": 0.0,  "C5219261": 270.0,
        "C705366": 270.0, "C724044": 270.0,
    }

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
        import jlc_orientation
        cls.tool = jlc_orientation
        cls.derived = jlc_orientation.derive(orientation.PART_NUMBER_FIELD)

    def _spec(self):
        with open(os.path.join(REPO_ROOT, "board", "manifest.json"),
                  encoding="utf-8") as handle:
            document = json.load(handle)
        return document["release_generation"]["cpl_orientation"]

    def test_every_offset_is_the_one_the_evidence_derives(self):
        for lcsc, expected in self.EXPECTED_OFFSETS.items():
            record = self.derived[lcsc]
            self.assertTrue(record["decisive"], lcsc)
            self.assertAlmostEqual(record["best_offset_deg"], expected,
                                   places=3, msg=lcsc)

    def test_the_committed_registry_is_the_derived_one(self):
        rows, refused = orientation.registry()
        self.assertEqual(refused, [])
        self.assertEqual(self._spec()["registry"], rows)

    def test_every_part_number_on_the_board_has_an_entry(self):
        board = self.tool.footprint_pads(self.tool.BOARD,
                                         orientation.PART_NUMBER_FIELD)
        covered = {row["lcsc"] for row in self._spec()["registry"]}
        self.assertEqual(sorted(board), sorted(covered))

    def test_the_polarised_two_pad_parts_do_not_share_an_offset(self):
        """The indicator and the clamp diode are both two-pad polarised
        parts, and they are fitted differently. Only evidence separates
        them."""
        self.assertNotEqual(self.EXPECTED_OFFSETS["C2286"],
                            self.EXPECTED_OFFSETS["C315992"])

    def test_editing_the_raw_body_is_caught(self):
        raw = self.tool.raw_path("C2286")
        with open(raw, "rb") as handle:
            body = handle.read()
        try:
            with open(raw, "wb") as handle:
                handle.write(body + b" ")
            problems, _pads = self.tool.verify("C2286")
            self.assertTrue(problems)
            self.assertIn("digest", " ".join(p["issue"] for p in problems))
        finally:
            with open(raw, "wb") as handle:
                handle.write(body)

    def test_editing_the_extract_cannot_move_an_offset(self):
        path = self.tool.extract_path("C2286")
        with open(path, "rb") as handle:
            original = handle.read()
        try:
            record = json.loads(original.decode("utf-8"))
            record["pads"] = {number: [[-x, -y] for x, y in points]
                              for number, points in record["pads"].items()}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
            derived = self.tool.derive(orientation.PART_NUMBER_FIELD)
            self.assertAlmostEqual(derived["C2286"]["best_offset_deg"], 180.0,
                                   places=3)
            self.assertTrue(derived["C2286"]["evidence_problems"])
        finally:
            with open(path, "wb") as handle:
                handle.write(original)

    def test_deriving_never_reaches_the_network(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("the offline path reached the network")

        saved = self.tool.fetch
        self.tool.fetch = refuse
        try:
            derived = self.tool.derive(orientation.PART_NUMBER_FIELD)
        finally:
            self.tool.fetch = saved
        self.assertEqual(len(derived), len(self.EXPECTED_OFFSETS))
        for lcsc, record in derived.items():
            self.assertEqual(record["evidence_problems"], [], lcsc)

    def test_the_shipped_angles_are_the_board_angles_plus_the_offsets(self):
        import csv

        import pcbnew
        board = pcbnew.LoadBoard(layout.BOARD_PATH)
        offsets = {row["lcsc"]: float(row["offset_deg"])
                   for row in self._spec()["registry"]}
        angle, number = {}, {}
        for footprint in board.GetFootprints():
            reference = footprint.GetReference()
            angle[reference] = footprint.GetOrientationDegrees()
            for field in footprint.GetFields():
                if field.GetName() == orientation.PART_NUMBER_FIELD:
                    number[reference] = field.GetText().strip()
        path = os.path.join(REPO_ROOT, "generated", "release", "cpl.csv")
        with open(path, newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        for row in rows:
            reference = row["Designator"]
            shipped = float(row["Rotation"])
            self.assertGreaterEqual(shipped, 0.0, reference)
            self.assertLess(shipped, 360.0, reference)
            want = (angle[reference] + offsets[number[reference]]) % 360.0
            self.assertAlmostEqual(shipped, want, places=3, msg=reference)


class Style(unittest.TestCase):
    def test_no_module_exceeds_the_line_length(self):
        offenders = []
        for name in sorted(os.listdir(os.path.join(REPO_ROOT, "design"))):
            if not name.endswith(".py"):
                continue
            path = os.path.join(REPO_ROOT, "design", name)
            with open(path, encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    if len(line.rstrip("\n")) > 79:
                        offenders.append("%s:%d" % (name, number))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
