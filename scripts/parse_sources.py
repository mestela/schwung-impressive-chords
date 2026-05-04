import os
import sys
import json
import gzip
import xml.etree.ElementTree as ET
from collections import defaultdict

base_dir = "/data/UserData/schwung/modules/midi_fx/impressive-chords"
sources_dir = os.path.join(base_dir, "sources")
presets_dir = os.path.join(base_dir, "presets")
module_json_path = os.path.join(base_dir, "module.json")

os.makedirs(sources_dir, exist_ok=True)
os.makedirs(presets_dir, exist_ok=True)

def parse_json(filepath, preset_name):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        if preset_name in data:
            return data[preset_name][0]
        return data
    except Exception as e:
        print(f"Error parsing JSON {filepath}: {e}")
        return None

def parse_adv(filepath):
    try:
        with gzip.open(filepath, 'rb') as f:
            content = f.read()
        # Find <Blob>
        start = content.find(b'<Blob>')
        end = content.find(b'</Blob>')
        if start == -1 or end == -1:
            return None
        hex_str = content[start+6:end].decode('utf-8').strip()
        hex_str = "".join(hex_str.split())
        # Hex decode
        try:
            data_str = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
        except:
            return None
        # Find JSON
        start_json = data_str.find('{')
        end_json = data_str.rfind('}')
        if start_json == -1 or end_json == -1:
            return None
        json_str = data_str[start_json:end_json+1]
        try:
            data = json.loads(json_str)
            if "Notes" in data:
                return data["Notes"]
        except:
            return None
    except Exception as e:
        print(f"Error parsing ADV {filepath}: {e}")
        return None
    return None

def parse_alc(filepath):
    try:
        with gzip.open(filepath, 'rb') as f:
            content = f.read()
        try:
            root = ET.fromstring(content)
        except Exception as e:
            print(f"XML parse error for {filepath}: {e}")
            return None
            
        unique_chords = []
        from collections import defaultdict
        
        for notes_container in root.iter('Notes'):
            if notes_container.find('KeyTracks') is not None:
                # This is a clip notes container!
                chords_by_time = defaultdict(list)
                for key_track in notes_container.iter('KeyTrack'):
                    midi_key_elem = key_track.find('MidiKey')
                    if midi_key_elem is not None:
                        pitch = int(midi_key_elem.get('Value'))
                        notes_elem = key_track.find('Notes')
                        if notes_elem is not None:
                            for note_event in notes_elem.iter('MidiNoteEvent'):
                                time = float(note_event.get('Time'))
                                time_key = round(time, 3)
                                chords_by_time[time_key].append(pitch)
                                
                # Group by time for THIS clip
                sorted_times = sorted(chords_by_time.keys())
                tolerance = 0.05
                current_chord = []
                current_time = -1
                
                for t in sorted_times:
                    if current_time == -1 or t - current_time <= tolerance:
                        current_chord.extend(chords_by_time[t])
                        if current_time == -1:
                            current_time = t
                    else:
                        sorted_c = sorted(list(set(current_chord)))
                        if sorted_c not in unique_chords:
                            unique_chords.append(sorted_c)
                        current_chord = list(chords_by_time[t])
                        current_time = t
                if current_chord:
                    sorted_c = sorted(list(set(current_chord)))
                    if sorted_c not in unique_chords:
                        unique_chords.append(sorted_c)
                        
        # Convert to format { "0": [notes], "1": [notes], ... }
        res = {}
        for i, chord in enumerate(unique_chords):
            res[str(i)] = chord
        return res
    except Exception as e:
        print(f"Error parsing ALC/ALS {filepath}: {e}")
        return None

# Scan sources
try:
    files = os.listdir(sources_dir)
except Exception as e:
    print(f"Error listing sources {sources_dir}: {e}")
    sys.exit(1)

processed_any = False

for filename in files:
    ext = os.path.splitext(filename)[1].lower()
    preset_name = os.path.splitext(filename)[0]
    display_name = preset_name.replace('_', ' ').title()
    filepath = os.path.join(sources_dir, filename)
    chords = None
    
    if ext == '.json':
        chords = parse_json(filepath, preset_name)
    elif ext == '.adv':
        chords = parse_adv(filepath)
    elif ext in ['.alc', '.als']:
        chords = parse_alc(filepath)
        
    if chords:
        out_path = os.path.join(presets_dir, preset_name + ".chords")
        try:
            with open(out_path, 'w') as f:
                f.write(f"Name: {display_name}\n")
                for key, notes in chords.items():
                    f.write(f"{key}: {','.join(map(str, notes))}\n")
            print(f"Processed {filename} -> {out_path}")
            processed_any = True
        except Exception as e:
            print(f"Error writing {out_path}: {e}")

# Update module.json if processed any
if processed_any:
    try:
        # Read all .chords files to get names
        chords_files = [f for f in os.listdir(presets_dir) if f.endswith('.chords')]
        preset_names = []
        for f in chords_files:
            with open(os.path.join(presets_dir, f), 'r') as file:
                line = file.readline()
                if line.startswith("Name:"):
                    preset_names.append(line[5:].strip())
                else:
                    preset_names.append(os.path.splitext(f)[0])
        preset_names.sort(key=str.lower)
        
        # Update module.json
        with open(module_json_path, 'r') as f:
            mod_data = json.load(f)
            
        # Find preset_index param
        for param in mod_data['capabilities']['ui_hierarchy']['levels']['root']['params']:
            if isinstance(param, dict) and param.get('key') == 'preset_index':
                param['max'] = len(preset_names) - 1
                break
                
        with open(module_json_path, 'w') as f:
            json.dump(mod_data, f, indent=2)
        print("Updated module.json with new presets")
        
        # Also write chain_params.json for C to read!
        chain_params = mod_data['capabilities']['ui_hierarchy']['levels']['root']['params']
        with open(os.path.join(base_dir, "chain_params.json"), 'w') as f:
            json.dump(chain_params, f, indent=2)
        print("Updated chain_params.json")
        
    except Exception as e:
        print(f"Error updating module.json or chain_params.json: {e}")
