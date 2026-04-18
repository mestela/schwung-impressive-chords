import json

input_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/impressive_chords.json"
output_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/schwung/src/modules/midi_fx/impressive-chords/dsp/impressive_chords_params.h"

with open(input_file, 'r') as f:
    data = json.load(f)

presets = list(data.keys())

params_obj = [
  {"key": "preset", "name": "Preset", "type": "enum", "options": presets},
  {"key": "base_note", "name": "Base Note", "type": "int", "min": 0, "max": 127, "step": 1},
  {"key": "transpose", "name": "Transpose", "type": "int", "min": -24, "max": 24, "step": 1},
  {"key": "invert", "name": "Invert", "type": "int", "min": -12, "max": 12, "step": 1},
  {"key": "strum", "name": "Strum", "type": "int", "min": 0, "max": 100, "step": 1},
  {"key": "tilt", "name": "Tilt", "type": "int", "min": -100, "max": 100, "step": 1},
  {"key": "articulate", "name": "Articulate", "type": "int", "min": 1, "max": 8, "step": 1},
  {"key": "length", "name": "Length", "type": "int", "min": 10, "max": 2000, "step": 10}
]

params_json = json.dumps(params_obj)

with open(output_file, 'w') as f:
    f.write("#ifndef IMPRESSIVE_CHORDS_PARAMS_H\n")
    f.write("#define IMPRESSIVE_CHORDS_PARAMS_H\n\n")
    
    f.write("const char *g_chain_params = \"")
    f.write(params_json.replace('"', '\\"'))
    f.write("\";\n\n")
    
    f.write("#endif\n")

print(f"Generated {output_file}")
