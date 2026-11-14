Go through the .md 

# Project: Gesture Recognition Magic Wand (EE 2361, UMN, Fall 2026)

## What it is
Handheld wand with an LIS3DH accelerometer. The PIC24 classifies the motion as one of
8 gestures, shows an icon on an 8x8 RGB LED matrix (WS2812), and controls a
color-changing light bulb. Deliverable is a reusable C library with ≥5 public functions,
documentation, and a demo.

## Hardware and constraints
- MCU: PIC24FJ64GA002, 16 MIPS (Fcy = 16 MHz), 64 KB flash, 8 KB RAM, NO FPU, NO DMA
- Toolchain: MPLAB X + XC16 [confirm version]
- LIS3DH over I2C [I2C1/I2C2? address 0x18 or 0x19], WHO_AM_I = 0x33
- Sampling: 100 Hz, ±4 g, FIFO stream mode; motion interrupt starts a 1.5 s capture window
- Pins: [fill in]
- Integer / fixed-point math only in runtime code. No float in the hot path, no malloc.
- Keep the RAM budget tight. Capture buffer is ~900 bytes (150 samples × 3 axes × int16).

## Gestures (class ids)
0 none, 1 swipe right, 2 swipe left, 3 raise, 4 push down, 5 circle CW,
6 circle CCW, 7 twist (wrist roll ~90° and back), 8 thrust.
Double tap is handled by the LIS3DH hardware click detection, not the classifier.
Axes: X = out the tip, Y = left, Z = up (board face-up, held like a TV remote).

## Team and ownership
- EVERYONE: LIS3DH driver, FIFO, interrupts, capture, UART raw streaming
- EVERYONE Python recording tool, training, export model → gesture_model.h
- EVERYONE: on-device feature extraction, fixed-point inference, confidence
  threshold, "learn gesture" (k-NN/DTW templates), verification vs Python
- EVERYONE: WS2812 matrix driver, icons/animations, light bulb control, demo

## My part: classifier pipeline
1. Features: split the window into 10 segments; per axis per segment compute mean and
   energy → ~60 int16 features. Must match the Python implementation exactly.
2. Model: small MLP (features → 16 hidden → 9 classes), int8 weights, int32 accumulators,
   ReLU, argmax. Weights/scales come from gesture_model.h.
3. Reject: if (top1 − top2) margin < threshold → GESTURE_UNKNOWN.
4. Learn mode: store a few template feature vectors per new class; k-NN on-device.
5. Test: same input vectors through Python and C must give identical outputs.
   Measure cycles (toggle a pin / Timer), RAM, and flash.

## Planned public API
void   gesture_init(uint8_t odr_hz, uint8_t range_g);
void   gesture_set_trigger(uint16_t threshold_mg);
bool   gesture_poll(void);                     // true when a capture window is ready
int8_t gesture_classify(uint8_t *confidence);  // class id or GESTURE_UNKNOWN
void   gesture_learn(uint8_t class_id);
void   gesture_set_reject(uint8_t min_conf);
void   gesture_stream_raw(bool on);

## Course rules that affect how you write code
- AI-written code MUST be clearly marked. Wrap anything you generate in
  // [AI-GENERATED: Claude Code] ... // [END AI-GENERATED]
  and keep a running list in AI_USAGE.md (file, function, what it does).
- Any borrowed code (e.g. reference drivers) must be cited in a comment and in the docs.
- Every public function needs a doc comment: purpose, args, return value.

## Style
- C99, one .c/.h pair per module (lis3dh, gesture, matrix, …)
- No blocking delays in library code; non-blocking poll functions
- Comment register writes with what each bit field does