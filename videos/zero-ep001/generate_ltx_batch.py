"""Generate EP01 short motion candidates with one local LTX 2.5 model load.

This uses the installed LTX Desktop weights at /Users/product/sex. Candidates
never enter the composition until the identity/hand/space review is complete.
"""
from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
SOURCE = Path('/Users/product/sex')
sys.path.insert(0, str(SOURCE))
import generate_soft_video as local_ltx


SHOTS = (
    ('lan_holds_door', 'lan_tick_close.png', 6, 2003),
    ('noah_explains', 'boy_lantern_close.png', 6, 2004),
    ('noah_destination', 'boy_lantern_close.png', 7, 2005),
    ('moon_outro', 'assets/ltx/moon_outro_start.png', 2, 2006),
)


def main() -> None:
    if sys.platform != 'darwin':
        raise RuntimeError('LTX generation needs macOS Metal')
    pending = []
    for shot in SHOTS:
        name = shot[0]
        output = PROJECT / 'assets/ltx' / f'{name}_candidate.mp4'
        approved = PROJECT / 'assets/ltx' / f'{name}_approved.mp4'
        if approved.exists() or output.exists():
            print(f'Skipping existing {approved if approved.exists() else output}', flush=True)
        else:
            pending.append(shot)
    if not pending:
        print('All shots already have approved or candidate files', flush=True)
        return
    os.environ.setdefault('MPS_SDPA_SKIP_CALIBRATION', '1')
    os.environ.setdefault('LTX_MPS_EXT_PREBUILT_DIR', str(local_ltx.EXTENSION))
    sys.path.insert(0, str(local_ltx.BACKEND))

    import torch
    import mps_prebuilt_ext
    mps_prebuilt_ext.setup_prebuilt_mps_extension()
    import services.patches.mps_sdpa_torch as mps_sdpa_torch
    mps_sdpa_torch.install()
    from api_types import ImageConditioningInput
    from frame_math import compute_num_frames
    from services.fast_video_pipeline.ltx_fast_video_pipeline import LTXFastVideoPipeline

    print('Loading local LTX model once for approved candidate list', flush=True)
    pipeline = LTXFastVideoPipeline.create(
        checkpoint_path=str(local_ltx.TRANSFORMER),
        gemma_root=str(local_ltx.GEMMA),
        upsampler_path=str(local_ltx.UPSAMPLER),
        device=torch.device('mps'),
        streaming_prefetch_count=None,
        video_vae_path=str(local_ltx.VIDEO_VAE),
        audio_vae_path=str(local_ltx.AUDIO_VAE),
        duration_head_path=str(local_ltx.DURATION_HEAD),
    )
    for name, image_name, duration, seed in pending:
        output = PROJECT / 'assets/ltx' / f'{name}_candidate.mp4'
        image = (PROJECT / image_name if '/' in image_name else
                 PROJECT.parent.parent / 'series/elevator_zero/assets' / image_name)
        prompt = (PROJECT / 'assets/ltx' / f'{name}_prompt.txt').read_text(encoding='utf-8').strip()
        if not image.is_file() or not prompt:
            raise RuntimeError(f'Missing image or prompt for {name}')
        print(f'Generating {name}: {duration}s, 576x1024, seed {seed}', flush=True)
        pipeline.generate(
            prompt=prompt, seed=seed, height=1024, width=576,
            num_frames=compute_num_frames(duration, 24), frame_rate=24.0,
            images=[ImageConditioningInput(path=str(image), frame_idx=0, strength=1.0)],
            output_path=str(output), guide_all_images=False,
        )
        print(f'Wrote {output}', flush=True)
        gc.collect()
        torch.mps.empty_cache()


if __name__ == '__main__':
    main()
