import unittest

from kie.capabilities import check_operation
from test_generated import load_plugin
import sys
from unittest.mock import patch


class TestModelControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_plugin()
        cls.generated = sys.modules['kie_next_testpkg.nodes.generated']

    def test_optional_prompt_and_reference_stay_optional_with_explicit_schema(self):
        op = {'title': 'Example Image To Video', 'endpoint': '/api/v1/jobs/createTask',
              'parameter_hints': {'prompt': {'type': 'string', 'required': False},
                                  'image_url': {'type': 'string', 'required': False},
                                  'duration': {'type': 'integer', 'minimum': 3, 'maximum': 30, 'default': 5}},
              'example_body': {'duration': 10}}
        inputs = self.generated._friendly_input_types(op, model='example/model')
        self.assertNotIn('prompt', inputs['required'])
        self.assertIn('image_url', inputs['optional'])
        self.assertEqual(inputs['optional']['duration'][1]['default'], 5)
        self.assertEqual(inputs['optional']['duration'][1]['max'], 30)

    def test_node_definition_never_resolves_remote_documentation(self):
        op = {'title': 'Unresolved model', 'label': 'Unresolved test entry', 'family': 'Video Models > Example'}
        node = self.generated.make_model_node(op)
        with patch.object(self.generated, 'resolve_operation', side_effect=AssertionError('Network resolution during UI metadata')):
            self.assertIsInstance(node.INPUT_TYPES(), dict)

    def test_keyframe_batch_is_native_image(self):
        inputs = self.generated._friendly_input_types({'title': 'Kling 4.0 Keyframes',
            'parameter_hints': {'keyframe_urls': {'type': 'array', 'maxItems': 8, 'required': False}}})
        self.assertEqual(inputs['optional']['keyframe_urls'][0], 'IMAGE')

    def test_invalid_example_does_not_add_an_unsupported_resolution(self):
        widget = self.generated._scalar_widget('resolution', '4k', {
            'parameter_hints': {'resolution': {'type': 'string', 'enum': ['720p', '1080p']}}})
        self.assertEqual(widget[0], ['720p', '1080p'])

    def test_reference_socket_count_follows_model_limit(self):
        inputs = self.generated._friendly_input_types({'title': 'Reference Video', 'parameter_hints': {
            'video_urls': {'type': 'array', 'maxItems': 1},
            'reference_audio_urls': {'type': 'array', 'maxItems': 5}}})
        self.assertIn('video_1', inputs['optional'])
        self.assertNotIn('video_2', inputs['optional'])
        self.assertIn('reference_audio_5', inputs['optional'])
        self.assertNotIn('reference_audio_6', inputs['optional'])

    def test_kling_rejects_missing_mentions_and_frame_duration_mismatch(self):
        payload = {'prompt': 'Move through @keyframe_2 to @last_frame', 'duration': 3,
                   'first_frame_url': 'https://example.com/first.png',
                   'keyframe_urls': ['https://example.com/k.png'] * 4}
        result = check_operation({'parameter_hints': {}}, payload, model='kling-4.0/keyframe-to-video')
        self.assertFalse(result['valid'])
        self.assertTrue(any('@last_frame' in error for error in result['errors']))
        self.assertTrue(any('total first/middle/last frames' in error for error in result['errors']))

    def test_kling_valid_mentions_and_frames(self):
        result = check_operation({'parameter_hints': {}}, {
            'prompt': 'Move from @first_frame through @keyframe_1 to @last_frame', 'duration': 3,
            'first_frame_url': 'https://example.com/first.png',
            'keyframe_urls': ['https://example.com/middle.png'],
            'last_frame_url': 'https://example.com/last.png'}, model='kling-4.0/keyframe-to-video')
        self.assertTrue(result['valid'])

    def test_input_mode_selects_exact_fields_and_checks_required_reference(self):
        op = {'endpoint': '/api/v1/jobs/createTask', 'title': 'Segment map',
              'input_schema': {'oneOf': [
                  {'title': 'Existing task', 'required': ['task_id'], 'properties': {'task_id': {'type': 'string'}}},
                  {'title': 'New image', 'required': ['image_url'], 'properties': {'image_url': {'type': 'string'}}}]},
              'parameter_hints': {'task_id': {'type': 'string'}, 'image_url': {'type': 'string'}},
              'example_body': {'task_id': 'old-task'}}
        inputs = self.generated._friendly_input_types(op, model='example/segment')
        self.assertEqual(inputs['required']['input_variant'][0], ['Existing task', 'New image'])
        payload = self.generated._build_payload(None, op, {'input_variant': 'Existing task', 'task_id': 'approved-task'}, model='example/segment', dry_run=True)
        self.assertEqual(payload, {'task_id': 'approved-task'})
        report = self.generated.preflight_model_inputs(op, 'example/segment', {'input_variant': 'New image'})
        self.assertFalse(report['valid'])
        self.assertTrue(any('image_url' in error for error in report['errors']))
