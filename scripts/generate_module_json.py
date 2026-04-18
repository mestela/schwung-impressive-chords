import json

input_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/impressive_chords.json"
output_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/schwung/src/modules/midi_fx/impressive-chords/module.json"

with open(input_file, 'r') as f:
    data = json.load(f)

presets = list(data.keys())

module_json = {
  "id": "impressive-chords",
  "name": "Impressive Chords",
  "abbrev": "IC",
  "version": "0.1.0",
  "author": "mestela",
  "builtin": True,
  "capabilities": {
    "chainable": True,
    "component_type": "midi_fx",
    "ui_hierarchy": {
      "levels": {
        "root": {
          "name": "Impressive Chords",
          "params": [
            {
              "key": "preset",
              "name": "Preset",
              "type": "enum",
              "options": presets,
              "default": 0
            },
            {
              "key": "base_note",
              "name": "Base Note",
              "type": "int",
              "min": 0,
              "max": 127,
              "default": 48,
              "step": 1
            },
            {
              "key": "transpose",
              "name": "Transpose",
              "type": "int",
              "min": -24,
              "max": 24,
              "default": 0,
              "step": 1
            },
            {
              "key": "invert",
              "name": "Invert",
              "type": "int",
              "min": -12,
              "max": 12,
              "default": 0,
              "step": 1
            },
            {
              "key": "strum",
              "name": "Strum",
              "type": "int",
              "min": 0,
              "max": 100,
              "default": 0,
              "step": 1
            },
            {
              "key": "tilt",
              "name": "Tilt",
              "type": "int",
              "min": -100,
              "max": 100,
              "default": 0,
              "step": 1
            },
            {
              "key": "articulate",
              "name": "Articulate",
              "type": "int",
              "min": 1,
              "max": 8,
              "default": 1,
              "step": 1
            },
            {
              "key": "length",
              "name": "Length",
              "type": "int",
              "min": 10,
              "max": 2000,
              "default": 200,
              "step": 10
            }
          ],
          "knobs": ["preset", "base_note", "transpose", "invert", "strum", "tilt", "articulate", "length"]
        }
      }
    }
  }
}

with open(output_file, 'w') as f:
    json.dump(module_json, f, indent=2)

print(f"Generated {output_file}")
