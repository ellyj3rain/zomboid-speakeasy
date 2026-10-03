import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import native_video as Video


class NativeVideoTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).parent / 'fixtures/native_video.json').read_text())
        self.value = deepcopy(self.fixture['manifest'])
        self.now = self.value['segments'][-1]['endCapturedAtUnixMs']

    def bytes(self, descriptor):
        return base64.b64decode(self.fixture['files'][descriptor['file']])

    def test_actual_encoded_fragment_preserves_clocks_and_independent_samples(self):
        Video.validate(self.value, now=self.now)
        info = Video.init_info(self.bytes(self.value['init']), self.value)
        self.assertEqual(Video.media_info(self.bytes(self.value['segments'][0]), self.value['segments'][0], info), 15)
        frame, sites = Video.acknowledged_frame(self.value, {'observerSequence': 0, 'capturedAtUnixMs': 0})
        self.assertEqual(frame['capturedAtUnixMs'], self.value['segments'][0]['endCapturedAtUnixMs'])
        self.assertEqual(sites, self.value['segments'][0]['sites'])

    def test_mixed_epoch_has_no_invented_camera_pose(self):
        self.value['segments'][0]['sites'] = []
        fallback = {'observerSequence': 2, 'capturedAtUnixMs': self.now}
        self.assertEqual(Video.acknowledged_frame(self.value, fallback), (fallback, None))

    def test_mixed_pose_retains_authoritative_crop_without_camera_acknowledgment(self):
        segment = self.value['segments'][0]
        segment['crops'] = [{key: site[key] for key in ('id', 'slot', 'left', 'top', 'width', 'height')}
                            for site in segment['sites']]
        Video.validate(self.value, now=self.now)
        segment['sites'] = []
        Video.validate(self.value, now=self.now)
        fallback = {'observerSequence': 2, 'capturedAtUnixMs': self.now}
        self.assertEqual(Video.acknowledged_frame(self.value, fallback), (fallback, None))
        segment['crops'] = []
        Video.validate(self.value, now=self.now)

    def test_crops_refuse_conflicting_pose_bounds_overlaps_and_extra_claims(self):
        original = self.value['segments'][0]
        original['crops'] = [{key: site[key] for key in ('id', 'slot', 'left', 'top', 'width', 'height')}
                             for site in original['sites']]
        changes = [lambda s: s['crops'][0].update(width=321), lambda s: s['crops'][0].update(slot=True),
                   lambda s: s['crops'][0].update(x=10), lambda s: s['crops'].append(deepcopy(s['crops'][0])),
                   lambda s: s['crops'][0].update(id='outside'), lambda s: s.update(crops=[]),
                   lambda s: s['crops'][0].update(left=.5), lambda s: s['crops'][0].update(slot=1)]
        for change in changes:
            value = deepcopy(self.value); change(value['segments'][0])
            with self.assertRaises(ValueError): Video.validate(value, now=self.now)
        value = deepcopy(self.value); value['segments'][0]['sites'] = []
        value['segments'][0]['crops'] = [original['crops'][0] | {'width': 200},
                                     original['crops'][0] | {'id': 'other', 'slot': 1, 'left': 150, 'width': 170}]
        with self.assertRaisesRegex(ValueError, 'overlaps'): Video.validate(value, now=self.now)

    def test_bad_identity_clocks_counts_geometry_and_types_are_refused(self):
        changes = [lambda v: v.update(streamId='../escape'),
                   lambda v: v['segments'][0].update(file='../outside.m4s'),
                   lambda v: v['segments'][0].update(endCapturedAtUnixMs=self.now + 2001),
                   lambda v: v['segments'][0].update(ptsStartMs=True),
                   lambda v: v['segments'][0]['sites'][0].update(left=321),
                   lambda v: v['segments'][0]['sites'][0].update(z=32),
                   lambda v: v['stats'].update(encodedFrames=181),
                   lambda v: v.update(init=None),
                   lambda v: v.update(message='C:/Users/someone/private/video.mp4')]
        for change in changes:
            value = deepcopy(self.value); change(value)
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)): Video.validate(value, now=self.now)

    def test_video_is_optional_before_initialization(self):
        value = self.value | {'state': 'starting', 'init': None, 'codecs': None, 'width': 0, 'height': 0, 'segments': []}
        Video.validate(value, now=self.now)

    def test_complete_boxes_with_empty_time_payload_are_contract_failures(self):
        import struct
        def box(kind, data=b''): return struct.pack('>I4s', len(data) + 8, kind.encode()) + data
        malformed = box('ftyp') + box('moov', box('mvex') + box('trak', box('mdia', box('mdhd'))))
        with self.assertRaisesRegex(ValueError, 'media time truncated'):
            Video.init_info(malformed, self.value)
        media = box('moof', box('traf', box('tfhd', bytes.fromhex('0002000000000001'))
                    + box('tfdt') + box('trun'))) + box('mdat')
        with self.assertRaisesRegex(ValueError, 'decode time truncated'):
            Video.media_info(media, self.value['segments'][0], {'track':1, 'duration':0, 'size':0, 'flags':0, 'timescale':1000})

    def test_codec_truncation_sample_flags_and_time_must_match(self):
        init = self.bytes(self.value['init']); descriptor = self.value['segments'][0]; media = self.bytes(descriptor)
        with self.assertRaises(ValueError): Video.init_info(init, self.value | {'codecs': 'avc1.42001f'})
        defaults = Video.init_info(init, self.value)
        with self.assertRaises(ValueError): Video.media_info(media[:-1], descriptor, defaults)
        with self.assertRaises(ValueError): Video.media_info(media, descriptor | {'durationMs': descriptor['durationMs'] + 10}, defaults)
        broken = bytearray(media); trun = broken.index(b'trun') + 4
        flags = int.from_bytes(broken[trun + 1:trun + 4], 'big')
        self.assertTrue(flags & 4)
        first_flag = trun + 8 + 4
        broken[first_flag:first_flag + 4] = (0x01010000).to_bytes(4, 'big')
        with self.assertRaises(ValueError): Video.media_info(bytes(broken), descriptor, defaults)

    def test_only_hashed_regular_immutable_files_are_relayed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); source = root / 'source'; destination = root / 'destination'
            source.mkdir(); destination.mkdir()
            for filename, data in self.fixture['files'].items(): (source / filename).write_bytes(base64.b64decode(data))
            relay = Video.VideoRelay(source, destination)
            result = relay.publish(self.value, now=self.now)
            self.assertEqual(result['schema'], 'mousecat.native-video/1')
            self.assertEqual(result['segments'], self.value['segments'])
            changed = deepcopy(self.value); changed['segments'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'filename reused'): relay.publish(changed, now=self.now)
            changed = deepcopy(self.value); changed['segments'][0]['ptsStartMs'] += 10
            with self.assertRaisesRegex(ValueError, 'filename reused'): relay.publish(changed, now=self.now)
            changed = deepcopy(self.value); changed['codecs'] = 'avc1.42001f'
            with self.assertRaisesRegex(ValueError, 'format reused'): relay.publish(changed, now=self.now)
            changed = deepcopy(self.value); changed['stats']['encodedFrames'] -= 1
            with self.assertRaisesRegex(ValueError, 'counts regressed'): relay.publish(changed, now=self.now)
            data = self.bytes(self.value['init']) + b'extra'
            (source / self.value['init']['file']).write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'hash'): Video.VideoRelay(source, destination).publish(self.value, now=self.now)


if __name__ == '__main__': unittest.main()
