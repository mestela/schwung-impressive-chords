import {
    Black, White, LightGrey, Red, Blue,
    MidiNoteOn, MidiNoteOff, MidiCC,
    MoveShift, MoveMainKnob, MovePads,
    MoveKnob1, MoveKnob8
} from '/data/UserData/schwung/shared/constants.mjs';

import {
    isNoiseMessage, isCapacitiveTouchMessage,
    setLED, clearAllLEDs, decodeDelta
} from '/data/UserData/schwung/shared/input_filter.mjs';

/* State */
let chordsData = null;
let presets = [];
let currentPresetIdx = 0;
let currentPreset = null;
let activeChords = {}; // Track active notes per pad

/* Display state */
let line1 = "Impressive Chords";
let line2 = "Loading...";
let line3 = "";
let line4 = "";

function drawUI() {
    clear_screen();
    print(2, 2, line1, 1);
    print(2, 18, line2, 1);
    print(2, 34, line3, 1);
    print(2, 50, line4, 1);
}

function displayMessage(l1, l2, l3, l4) {
    if (l1 !== undefined) line1 = l1;
    if (l2 !== undefined) line2 = l2;
    if (l3 !== undefined) line3 = l3;
    if (l4 !== undefined) line4 = l4;
}

function loadChords() {
    const baseDir = "/data/UserData/schwung/modules/midi_fx/impressive-chords";
    const sourcesDir = baseDir + "/sources";
    const presetsDir = baseDir + "/presets";
    
    host_ensure_dir(sourcesDir);
    host_ensure_dir(presetsDir);
    
    // 1. Process files in sources
    const listFile = "/tmp/sources_list.txt";
    host_system_cmd(`ls ${sourcesDir} > ${listFile}`);
    const listContent = host_read_file(listFile);
    
    if (listContent) {
        const files = listContent.split('\n').filter(f => f.trim() !== '');
        for (const filename of files) {
            const filepath = sourcesDir + "/" + filename;
            const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
            const presetName = filename.substring(0, filename.lastIndexOf('.'));
            
            try {
                let chords = null;
                
                if (ext === '.json') {
                    const content = host_read_file(filepath);
                    const data = JSON.parse(content);
                    if (data[presetName]) {
                        chords = data[presetName][0];
                    } else {
                        chords = data;
                    }
                } else if (ext === '.adv' || ext === '.als') {
                    const xmlFile = "/tmp/extracted.xml";
                    host_system_cmd(`sh -c "gzip -d -c '${filepath}' > ${xmlFile}"`);
                    const xmlContent = host_read_file(xmlFile);
                    
                    if (xmlContent) {
                        const blobMatch = xmlContent.match(/<Blob>([\s\S]*?)<\/Blob>/);
                        if (blobMatch) {
                            const hexStr = blobMatch[1].replace(/\s+/g, '');
                            let str = '';
                            for (let i = 0; i < hexStr.length; i += 2) {
                                str += String.fromCharCode(parseInt(hexStr.substr(i, 2), 16));
                            }
                            const startIdx = str.indexOf('{');
                            const endIdx = str.lastIndexOf('}');
                            if (startIdx !== -1 && endIdx !== -1) {
                                const jsonStr = str.substring(startIdx, endIdx + 1);
                                const data = JSON.parse(jsonStr);
                                if (data.Notes) {
                                    chords = data.Notes;
                                }
                            }
                        }
                    }
                } else if (ext === '.alc') {
                    const xmlFile = "/tmp/extracted.xml";
                    host_system_cmd(`sh -c "gzip -d -c '${filepath}' > ${xmlFile}"`);
                    const xmlContent = host_read_file(xmlFile);
                    
                    if (xmlContent) {
                        const keyTrackRegex = /<KeyTrack[^>]*>([\s\S]*?)<\/KeyTrack>/g;
                        const midiKeyRegex = /<MidiKey Value="(\d+)"/;
                        
                        let match;
                        const chordsByTime = {};
                        
                        while ((match = keyTrackRegex.exec(xmlContent)) !== null) {
                            const block = match[1];
                            const keyMatch = block.match(midiKeyRegex);
                            if (keyMatch) {
                                const pitch = parseInt(keyMatch[1]);
                                
                                const eventRegex = /<MidiNoteEvent Time="([\d.]+)"/g;
                                let eventMatch;
                                while ((eventMatch = eventRegex.exec(block)) !== null) {
                                    const time = parseFloat(eventMatch[1]);
                                    const timeKey = Math.round(time * 1000) / 1000;
                                    if (!chordsByTime[timeKey]) chordsByTime[timeKey] = [];
                                    chordsByTime[timeKey].push(pitch);
                                }
                            }
                        }
                        
                        const sortedTimes = Object.keys(chordsByTime).map(Number).sort((a, b) => a - b);
                        const tolerance = 0.05;
                        const groupedChords = [];
                        let currentChord = [];
                        let currentTime = -1;
                        
                        for (const t of sortedTimes) {
                            if (currentTime === -1 || t - currentTime <= tolerance) {
                                currentChord.push(...chordsByTime[t]);
                                if (currentTime === -1) currentTime = t;
                            } else {
                                groupedChords.push(Array.from(new Set(currentChord)).sort((a, b) => a - b));
                                currentChord = [...chordsByTime[t]];
                                currentTime = t;
                            }
                        }
                        if (currentChord.length > 0) {
                            groupedChords.push(Array.from(new Set(currentChord)).sort((a, b) => a - b));
                        }
                        
                        const uniqueChords = [];
                        for (const chord of groupedChords) {
                            const chordStr = chord.join(',');
                            if (!uniqueChords.some(c => c.join(',') === chordStr)) {
                                uniqueChords.push(chord);
                            }
                        }
                        
                        chords = {};
                        for (let i = 0; i < uniqueChords.length; i++) {
                            chords[i.toString()] = uniqueChords[i];
                        }
                    }
                }
                
                if (chords) {
                    let output = `Name: ${presetName}\n`;
                    for (const key in chords) {
                        const notes = chords[key];
                        if (Array.isArray(notes)) {
                            output += `${key}: ${notes.join(',')}\n`;
                        }
                    }
                    host_write_file(presetsDir + "/" + presetName + ".chords", output);
                }
            } catch (e) {
                console.log(`Error processing ${filename}: ${e}`);
            }
        }
    }
    
    // 2. Load from presets directory
    chordsData = {};
    presets = [];
    
    const presetsListFile = "/tmp/presets_list.txt";
    host_system_cmd(`ls ${presetsDir} > ${presetsListFile}`);
    const presetsListContent = host_read_file(presetsListFile);
    
    if (presetsListContent) {
        const files = presetsListContent.split('\n').filter(f => f.trim() !== '');
        for (const filename of files) {
            if (filename.endsWith('.chords')) {
                const presetName = filename.substring(0, filename.lastIndexOf('.'));
                const content = host_read_file(presetsDir + "/" + filename);
                if (content) {
                    const lines = content.split('\n');
                    const chords = {};
                    let realName = presetName;
                    for (const line of lines) {
                        if (line.startsWith("Name: ")) {
                            realName = line.substring(6).trim();
                            continue;
                        }
                        const parts = line.split(':');
                        if (parts.length === 2) {
                            const idx = parts[0].trim();
                            const notes = parts[1].split(',').map(Number);
                            chords[idx] = notes;
                        }
                    }
                    chordsData[realName] = [chords]; // Keep array wrapper for compatibility
                    presets.push(realName);
                }
            }
        }
    }
    
    presets.sort();
    
    // 3. Update module.json
    try {
        const moduleJsonPath = baseDir + "/module.json";
        const moduleJsonContent = host_read_file(moduleJsonPath);
        if (moduleJsonContent) {
            const moduleData = JSON.parse(moduleJsonContent);
            let found = false;
            for (const param of moduleData.capabilities.ui_hierarchy.levels.root.params) {
                if (param.key === 'preset') {
                    param.options = presets;
                    found = true;
                    break;
                }
            }
            if (found) {
                host_write_file(moduleJsonPath, JSON.stringify(moduleData, null, 2));
                console.log("Updated module.json with new presets.");
            }
        }
    } catch (e) {
        console.log("Error updating module.json: " + e);
    }
    
    if (presets.length > 0) {
        currentPreset = presets[currentPresetIdx];
        displayMessage("Impressive Chords", currentPreset, "Ready", "");
        updatePads();
    } else {
        displayMessage("Impressive Chords", "No presets found", "", "");
    }
}

function updatePads() {
    clearAllLEDs();
    if (!currentPreset || !chordsData) return;
    
    const chords = chordsData[currentPreset][0]; // Assuming structure is [ { "0": [...] } ]
    if (!chords) return;
    
    // Light up pads that have chords
    for (let i = 0; i < MovePads.length; i++) {
        const padNote = MovePads[i];
        const chordIdx = i.toString();
        if (chords[chordIdx]) {
            setLED(padNote, LightGrey);
        }
    }
}

function playChord(chordIdx, isOn, velocity) {
    if (!currentPreset || !chordsData) return;
    const chords = chordsData[currentPreset][0];
    const chord = chords[chordIdx.toString()];
    
    if (!chord) return;
    
    const status = isOn ? MidiNoteOn : MidiNoteOff;
    const type = isOn ? 0x9 : 0x8; // Status type without channel
    
    if (isOn) {
        activeChords[chordIdx] = chord;
        displayMessage(undefined, undefined, `Playing Chord ${chordIdx}`, chord.join(", "));
    } else {
        delete activeChords[chordIdx];
        displayMessage(undefined, undefined, "", "");
    }
    
    for (const note of chord) {
        // Send to internal Move (cable 0)
        move_midi_internal_send([type, status, note, velocity]);
    }
}

globalThis.onMidiMessageExternal = function (data) {
    // Handle external MIDI if needed
};

globalThis.onMidiMessageInternal = function (data) {
    if (isNoiseMessage(data)) return;
    if (isCapacitiveTouchMessage(data)) return;

    const status = data[0] & 0xF0;
    const d1 = data[1];
    const d2 = data[2];

    const isNote = status === MidiNoteOn || status === MidiNoteOff;
    const isNoteOn = status === MidiNoteOn;
    const isCC = status === MidiCC;

    if (isNote) {
        const note = d1;
        const velocity = d2;

        if (MovePads.includes(note)) {
            const padIdx = MovePads.indexOf(note);
            const isOn = isNoteOn && velocity > 0;
            
            playChord(padIdx, isOn, velocity);
            
            // Feedback LED
            if (isOn) {
                setLED(note, White);
            } else {
                setLED(note, LightGrey);
            }
            return;
        }
    }

    if (isCC) {
        const ccNumber = d1;
        const value = d2;

        // Jog wheel to change presets
        if (ccNumber === MoveMainKnob) {
            const delta = decodeDelta(value);
            if (delta !== 0 && presets.length > 0) {
                currentPresetIdx = (currentPresetIdx + delta + presets.length) % presets.length;
                currentPreset = presets[currentPresetIdx];
                displayMessage(undefined, currentPreset, "Ready", "");
                updatePads();
            }
            return;
        }
    }
};

globalThis.init = function () {
    console.log("Impressive Chords module starting...");
    displayMessage("Impressive Chords", "Loading data...", "", "");
    loadChords();
};

globalThis.tick = function () {
    drawUI();
};
