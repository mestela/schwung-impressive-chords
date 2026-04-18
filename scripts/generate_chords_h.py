import json

input_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/impressive_chords.json"
output_file = "/Users/mattestela/.gemini/jetski/scratch/schwung/schwung/src/modules/midi_fx/impressive-chords/dsp/impressive_chords_data.h"

with open(input_file, 'r') as f:
    data = json.load(f)

with open(output_file, 'w') as f:
    f.write("#ifndef IMPRESSIVE_CHORDS_DATA_H\n")
    f.write("#define IMPRESSIVE_CHORDS_DATA_H\n\n")
    
    f.write("typedef struct {\n")
    f.write("    int notes[12];\n")
    f.write("    int count;\n")
    f.write("} chord_def_t;\n\n")
    
    f.write("typedef struct {\n")
    f.write("    const char *name;\n")
    f.write("    chord_def_t chords[48];\n")
    f.write("} preset_def_t;\n\n")
    
    f.write(f"#define NUM_PRESETS {len(data)}\n\n")
    
    f.write("const preset_def_t g_presets[NUM_PRESETS] = {\n")
    
    for preset_name, preset_data in data.items():
        f.write("    {\n")
        f.write(f'        "{preset_name}",\n')
        f.write("        {\n")
        
        # preset_data is a list containing a dict
        chords = preset_data[0] if isinstance(preset_data, list) else preset_data
        
        for i in range(48):
            chord_idx = str(i)
            if chord_idx in chords:
                notes = chords[chord_idx]
                count = len(notes)
                # Pad with zeros to 12 elements
                padded_notes = notes + [0] * (12 - count)
                notes_str = ", ".join(map(str, padded_notes))
                f.write(f"            {{ {{{notes_str}}}, {count} }},\n")
            else:
                # Empty chord
                f.write("            {{ {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0} }, 0 },\n")
                
        f.write("        }\n")
        f.write("    },\n")
        
    f.write("};\n\n")
    f.write("#endif\n")

print(f"Generated {output_file}")
