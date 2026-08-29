# Media QA / Subtitle / Privacy-Redaction Services

A separate service lane for small media-production tasks that can be scoped, checked, and delivered without pretending that automation removes the need for human review.

The public tools linked below are working proof of the QA methods used in this lane. They do not claim customer outcomes that have not happened.

## Subtitle / Transcript QA

**Reference price: from ¥1,500 per small delivery**

Suitable for short-form jobs such as:

- SRT structural QA
- subtitle numbering / timing checks
- empty or malformed cue detection
- duplicate / non-monotonic cue review
- optional client-specified CPS and maximum-duration checks
- transcript cleanup or formatting when the source material and delivery rules are provided

Public proof:

- [`tools/srt_doctor.py`](./tools/srt_doctor.py)
- [`tools/test_srt_doctor.py`](./tools/test_srt_doctor.py)

SRT Doctor has automated regression coverage for malformed indexes, oversized numeric indexes, invalid timing, false-overlap edge cases, duplicate indexes, empty text, invalid durations, and non-finite pacing thresholds.

Human language quality, speaker identification, translation quality, accessibility compliance, and final client acceptance still require review against the actual delivery specification.

## Static Video Privacy Blur / Mosaic Assistance

**Reference price: from ¥2,500 per short clip / bounded redaction plan**

Suitable when the redaction targets and time ranges can be specified explicitly, for example:

- a fixed screen region containing private information
- a license plate or display area that remains in a known rectangle for a bounded time range
- a short set of manually reviewed time / rectangle redaction instructions
- preparing and checking an FFmpeg blur plan before final rendering

Public proof:

- [`tools/video_redaction_filter.py`](./tools/video_redaction_filter.py)
- [`tools/test_video_redaction_filter.py`](./tools/test_video_redaction_filter.py)
- [`tools/examples/video-redaction-plan.json`](./tools/examples/video-redaction-plan.json)

The public helper validates time ranges, coordinates, crop dimensions, blur-radius constraints, and non-finite values, then emits a reviewable FFmpeg command. It does **not** perform face detection, person tracking, automatic censoring decisions, or network uploads.

Moving targets, long-form footage, frame-accurate tracking, or high-volume production are quoted separately because they require additional manual review or a different workflow.

## Small Media Preflight Bundle

**Reference price: from ¥3,800**

For small deliveries that need both text and privacy checks, for example:

- one short clip plus matching SRT
- subtitle structural QA
- bounded privacy-redaction plan review
- a concise issue report before final delivery

This is a preflight / production-assistance service, not a guarantee that a platform, broadcaster, client, or accessibility standard will accept the final media.

## Inquiry

For now, open a GitHub Issue in this repository with a **non-confidential** description of:

1. media type and approximate duration
2. desired output format
3. subtitle / transcript language
4. redaction targets, if any
5. deadline
6. any client-specific QA rules

Do not post private footage, personal data, passwords, API keys, contracts, private download links, or confidential client material in a public issue. Use the issue only to discuss scope; private transfer details can be agreed after scope is confirmed.

---

## 日本語

字幕・文字起こし・短尺動画のプライバシー処理を、AI/RAG開発とは別の小さな制作支援レーンとして扱います。

対応候補:

- SRTの構造チェック、番号・タイムコード・重複・空字幕の確認
- 指定ルールがある場合のCPS / 最大表示時間チェック
- 文字起こし原稿の整形・修正
- 時間範囲と矩形が明示できる短尺動画のぼかし / モザイク作業補助
- 字幕と動画をまとめた納品前チェック

参考価格:

- 字幕 / 文字起こしQA: **¥1,500〜**
- 短尺動画の静的ぼかし / モザイク補助: **¥2,500〜**
- 小規模メディア納品前チェック: **¥3,800〜**

公開済みのSRT DoctorとVideo Redaction Filter Plannerを技術証拠として利用します。自動判定だけで納品品質を保証せず、案件ごとの指定と人間の最終確認を前提にします。
