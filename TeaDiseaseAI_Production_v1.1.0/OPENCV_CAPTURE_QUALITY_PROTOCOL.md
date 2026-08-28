# OpenCV Capture Quality Validation Protocol

## Purpose

Validate the image-quality gate on the customer's actual field devices before fixing production thresholds. This protocol evaluates **capture usability**, not disease accuracy.

## Minimum validation set

Use at least 100–200 customer/local images, preferably across multiple estates, operators and devices. Include:

- clear daylight photographs;
- shade / cloudy light;
- mildly dark photographs;
- direct glare / bright backgrounds;
- motion blur and focus blur;
- leaves filling the frame and leaves photographed from too far away;
- cluttered vegetation backgrounds;
- healthy and diseased leaves across the supported classes;
- portrait and landscape phone orientation;
- multiple phone models if they will be used operationally.

## Ground truth for quality

For each image, a reviewer should label only the capture as one of:

- **Usable** — suitable for AI visual screening;
- **Usable with caution** — AI may run, but human review should be prioritised;
- **Retake required** — image is too poor for screening.

Do not use the AI disease prediction to decide the quality label.

## Metrics to review

Compare reviewer labels with:

- `quality_score`;
- `grade`;
- `blur_variance`;
- `brightness_mean`;
- `dark_ratio` / `bright_ratio`;
- `contrast_std`;
- `leaf_like_coverage` and `center_leaf_like_coverage` advisories;
- hard-fail reasons;
- warnings.

## Acceptance goal

The priority is to minimise two operational errors:

1. **False acceptance** — a clearly unusable photo is allowed into disease inference.
2. **False rejection** — a normal usable field photo is unnecessarily blocked.

Thresholds must be chosen from the local validation evidence, not from appearance alone.

## Configuration controls

All thresholds are configurable in `.env`:

- `QUALITY_MIN_HARD_SIDE`
- `QUALITY_MIN_RECOMMENDED_SIDE`
- `QUALITY_BLUR_HARD_THRESHOLD`
- `QUALITY_BLUR_WARN_THRESHOLD`
- `QUALITY_BRIGHTNESS_HARD_LOW`
- `QUALITY_BRIGHTNESS_WARN_LOW`
- `QUALITY_BRIGHTNESS_WARN_HIGH`
- `QUALITY_BRIGHTNESS_HARD_HIGH`
- `QUALITY_CLIP_WARN_RATIO`
- `QUALITY_CLIP_HARD_RATIO`
- `QUALITY_CONTRAST_WARN_THRESHOLD`
- `QUALITY_LEAF_COVERAGE_WARN_THRESHOLD`
- `QUALITY_CENTER_COVERAGE_WARN_THRESHOLD`
- `QUALITY_SCORE_HARD_MIN`
- `QUALITY_INFERENCE_MAX_SIDE`

## Change control

After customer acceptance, record:

- OpenCV version;
- quality-engine version;
- accepted `.env` thresholds;
- validation dataset/date;
- reviewer/approver;
- model version and model SHA-256;
- application version.

Any later change to thresholds, preprocessing or OpenCV major version should trigger a targeted revalidation.
