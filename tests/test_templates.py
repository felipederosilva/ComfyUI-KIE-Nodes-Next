import json
import pathlib
import unittest

from test_generated import load_plugin


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_guided_workflows_have_valid_nodes_and_links(self):
        for path in sorted((ROOT / "templates").glob("*.json")):
            with self.subTest(template=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertFalse(data["extra"]["kie_next_template"]["spends_credits"])
                nodes = {node["id"]: node for node in data["nodes"]}
                self.assertEqual(len(nodes), len(data["nodes"]))
                for node in nodes.values():
                    if node["type"] not in {"LoadAudio", "LoadImage"}:
                        self.assertIn(node["type"], self.plugin.NODE_CLASS_MAPPINGS)
                        definition = self.plugin.NODE_CLASS_MAPPINGS[node["type"]]
                        inputs = definition.INPUT_TYPES()
                        sockets = {**inputs.get("required", {}), **inputs.get("optional", {})}
                        for socket in node["inputs"]:
                            self.assertIn(socket["name"], sockets)
                            self.assertEqual(socket["type"], sockets[socket["name"]][0])
                        for index, socket in enumerate(node["outputs"]):
                            self.assertEqual(socket["type"], definition.RETURN_TYPES[index])
                ids = set()
                for link_id, source_id, source_slot, target_id, target_slot, kind in data["links"]:
                    self.assertNotIn(link_id, ids)
                    ids.add(link_id)
                    source = nodes[source_id]["outputs"][source_slot]
                    target = nodes[target_id]["inputs"][target_slot]
                    self.assertEqual(source["type"], kind)
                    self.assertEqual(target["type"], kind)
                    self.assertIn(link_id, source["links"])
                    self.assertEqual(link_id, target["link"])
                self.assertEqual(data["last_link_id"], max(ids))
