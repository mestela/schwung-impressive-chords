# Impressive Chords for Schwung

This is a MIDI FX module for Schwung that generates impressive chords with strumming, tilt, and articulation controls. It's a recreation of Expressive Chords, a M4L device for Ableton Live (not a port).

Demo: https://www.youtube.com/watch?v=seM7PpPqsQk

## Inspiration and Process
This module was inspired by the "Expressive Chords" concept. The chord presets were extracted from the source data and recreated in this native C implementation to provide dynamic chord generation, strumming, tilting, and articulation.

Renamed to "Impressive Chords" to clarify that it is unaffiliated with the official Ableton project.

## Installation

You can install this module directly from this repository on your Move device:

```bash
./scripts/install.sh install-module-github mestela/schwung-impressive-chords
```

## Parameters

- **Preset**: Select from your available chord presets using the fullscreen browser.
- **Base Note**: The MIDI note that triggers the chord.
- **Transpose**: Transpose the output notes.
- **Invert**: Shift notes up or down by octave (-12 to +12).
- **Strum**: Delay between notes in milliseconds (0-100ms).
- **Tilt**: Velocity ramp across notes (higher notes louder or softer).
- **Articulate**: Different strum orders (1: Low to High, 2: Outside-In, 3: High to Low, 4: Even/Odd, 5: Inside-Out, 6: Odd/Even, 7: Random).
- **Length**: Control length of notes (10-2000ms).
- **Retrigger**: Clock-synced retriggering (0 Off, 1 1B, 2 1/2B, etc.).
- **Timing**: Straight, Dotted, Triplet.
- **Choke**: Cut previous notes on retrigger or new note (0 or 1).
- **Notes Limit**: Force only this number of notes to play (0-12, 0 = no limit).
- **Fit Strum**: Fit the strum into the retrig length (0 or 1).
- **Gate**: Kill notes on pad release (0 or 1).

## Dynamic Chords Loading

Starting with v0.1.22, Impressive Chords supports loading chord sets dynamically at runtime from various formats.

### Supported Formats
- **.json**: Standard JSON files containing chord mappings.
- **.adv / .als**: Ableton Device Presets or Live Sets. The module will automatically extract the chords from the gzipped XML.
- **.alc**: Ableton Clips. The module will extract unique chords from the MIDI notes in the clip by grouping notes that occur within 50ms of each other.

### How to add custom chords:
1. Connect to your Move device via SSH/SFTP.
2. Place your files in the `sources` directory:
   `/data/UserData/schwung/modules/midi_fx/impressive-chords/sources/`
3. Turn the **`Scan Presets`** knob to **`1`** on the device to trigger the scan!
4. The module will parse the files and update the preset list dynamically.
5. Because it uses the dedicated Preset Browser UI, there is no limit on the number of presets you can have!

### Custom File Format (.chords)
The simplified format used internally and loaded by the C DSP engine is a simple line-based format:
```
Name: My Custom Chord Set
0: 60,64,67
1: 62,65,69
```
You can also write these files directly and place them in the `presets` directory!

## Roland J-6 Chord Pack

The bundled presets include all 100 factory chord sets from the Roland J-6,
transcribed from Roland's official [Chord Set List](https://static.roland.com/manuals/J-6_manual_v102/eng/28645807.html).
Each `J-6` preset maps the instrument's 12 key buttons to trigger notes 0-11 in
Impressive Chords. The published voicings are preserved and ordered low-to-high
for predictable strumming.

To regenerate the pack from Roland's current page:

```bash
python3 scripts/import_roland_j6.py
```

## Source Code

The source code is available in this repository for reference.
