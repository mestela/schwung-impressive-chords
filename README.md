# Impressive Chords for Schwung

This is a MIDI FX module for Schwung that generates impressive chords with strumming, tilt, and articulation controls. It's a port of Expressive Chords, a M4L device for Ableton Live.

## Inspiration and Process
This module was inspired by the "Expressive Chords" concept. The chord presets were extracted from the source data and ported to this native C implementation to provide dynamic chord generation, strumming, tilting, and articulation.

Renamed to "Impressive Chords" to clarify that it is unaffiliated with the official Ableton project.

## Installation

You can install this module directly from this repository on your Move device:

```bash
./scripts/install.sh install-module-github mestela/schwung-impressive-chords
```

## Parameters

- **Preset**: Select from 52 different chord presets (Indie Jazz, Guitar Voicings, etc.).
- **Base Note**: The MIDI note that triggers the chord (0-127, default 48).
- **Transpose**: Transpose the output notes (-24 to +24 semitones).
- **Invert**: Shift notes up or down by octave (-12 to +12).
- **Strum**: Delay between notes in milliseconds (0-100ms).
- **Tilt**: Velocity ramp across notes (-100 to +100; higher notes louder or softer).
- **Articulate**: Different strum orders (1: Low to High, 2: Outside-In, 3: High to Low, 4: Even/Odd, 5: Inside-Out, 6: Odd/Even, 7: Random).
- **Length**: Control length of notes (10-2000ms).

## Source Code

The source code is available in this repository for reference.
