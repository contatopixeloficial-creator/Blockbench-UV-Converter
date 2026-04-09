import json
import math
import os
import random
import string
import glob
from PIL import Image

random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
OUTPUT_NAME = f'converted_model_{random_suffix}'
MAX_TEXTURE_SIZE = 8192 

def next_power_of_2(n):
    if n <= 0: return 16
    return 2 ** math.ceil(math.log2(n))

def get_power_of_2_multiplier(density):
    # Transforma a densidade necessária numa escala de "dobras" (1x, 2x, 4x, 8x...)
    if density <= 1: return 1
    return 2 ** math.ceil(math.log2(density))

def get_layout_and_uv_coords(face, off_x, off_y, sx, sy, sz):
    if face == 'up':      lx, ly, lw, lh = sz, 0, sx, sz
    elif face == 'down':  lx, ly, lw, lh = sz + sx, 0, sx, sz
    elif face == 'east':  lx, ly, lw, lh = 0, sz, sz, sy        
    elif face == 'north': lx, ly, lw, lh = sz, sz, sx, sy
    elif face == 'west':  lx, ly, lw, lh = sz + sx, sz, sz, sy  
    elif face == 'south': lx, ly, lw, lh = 2 * sz + sx, sz, sx, sy
    else: return None, None

    uv_array = [off_x + lx, off_y + ly, off_x + lx + lw, off_y + ly + lh]
    return (lx, ly, lw, lh), uv_array

def convert():
    print("==================================================")
    print("      BLOCKBENCH AUTO-BAKE UV CONVERTER V8.0      ")
    print("   (Power-of-2 Scaling & Zero-Area Clamp Fixes)   ")
    print("==================================================\n")

    bbmodels = [f for f in glob.glob("*.bbmodel") if not f.startswith("converted_model_")]
    pngs = [f for f in glob.glob("*.png") if not f.startswith("converted_model_")]

    if len(bbmodels) == 0:
        print("[ERROR] No model (.bbmodel) found in this folder!")
        input("\nPress ENTER to exit...")
        return
    if len(pngs) == 0:
        print("[ERROR] No texture (.png) found in this folder!")
        input("\nPress ENTER to exit...")
        return

    MODEL_NAME = bbmodels[0]
    TEXTURE_NAME = pngs[0]

    print(f"[FILES DETECTED]")
    print(f"-> Model:   {MODEL_NAME}")
    print(f"-> Texture: {TEXTURE_NAME}\n")

    try:
        with open(MODEL_NAME, 'r', encoding='utf-8') as f:
            data = json.load(f)
        img_orig = Image.open(TEXTURE_NAME).convert("RGBA")
    except Exception as e:
        print(f"[FATAL ERROR] Could not read original files. Details: {e}")
        input("\nPress ENTER to exit...")
        return

    res_uv_orig_w = data.get('resolution', {}).get('width', 16)
    res_uv_orig_h = data.get('resolution', {}).get('height', 16)
    
    escala_x_orig = img_orig.width / res_uv_orig_w
    escala_y_orig = img_orig.height / res_uv_orig_h

    cubes = []
    fixed_cubes_count = 0
    max_required_density = 1.0 
    
    # PASSO 1: Analisar todas as faces e descobrir quem precisa da maior resolução
    for el in data.get('elements', []):
        if 'faces' not in el: continue

        for cursed_key in ['autouv', 'auto_uv']:
            if cursed_key in el: del el[cursed_key]
            for face_data in el['faces'].values():
                if cursed_key in face_data: del face_data[cursed_key]

        sx_raw = abs(el['to'][0] - el['from'][0])
        sy_raw = abs(el['to'][1] - el['from'][1])
        sz_raw = abs(el['to'][2] - el['from'][2])

        min_axis = min(sx_raw, sy_raw, sz_raw)
        
        if min_axis < 1.0:
            deficit = 1.0 - min_axis
            expansion = deficit / 2.0
            fixed_cubes_count += 1

            for i in range(3):
                if el['to'][i] >= el['from'][i]:
                    el['from'][i] -= expansion
                    el['to'][i] += expansion
                else:
                    el['from'][i] += expansion
                    el['to'][i] -= expansion
            
            el['inflate'] = el.get('inflate', 0) - expansion

        sx_uv = max(1, round(abs(el['to'][0] - el['from'][0])))
        sy_uv = max(1, round(abs(el['to'][1] - el['from'][1])))
        sz_uv = max(1, round(abs(el['to'][2] - el['from'][2])))

        w_nec = 2 * sz_uv + 2 * sx_uv
        h_nec = sz_uv + sy_uv

        for face_name, face_data in el['faces'].items():
            if 'uv' not in face_data: continue
            
            old_uv = face_data['uv']
            crop_w_px = abs(old_uv[2] - old_uv[0]) * escala_x_orig
            crop_h_px = abs(old_uv[3] - old_uv[1]) * escala_y_orig
            
            layout_data, _ = get_layout_and_uv_coords(face_name, 0, 0, sx_uv, sy_uv, sz_uv)
            if not layout_data: continue
            
            _, _, lw_uv, lh_uv = layout_data
            
            if lw_uv > 0: max_required_density = max(max_required_density, crop_w_px / lw_uv)
            if lh_uv > 0: max_required_density = max(max_required_density, crop_h_px / lh_uv)

        if w_nec > 0 and h_nec > 0:
            cubes.append({
                'el': el, 
                'sx_uv': sx_uv, 'sy_uv': sy_uv, 'sz_uv': sz_uv,
                'w': w_nec, 'h': h_nec
            })

    cubes.sort(key=lambda c: c['h'], reverse=True)

    if not cubes: 
        print("[ERROR] The model has no valid 3D blocks.")
        input("\nPress ENTER to exit...")
        return

    # PASSO 2: Criar o Grid Lógico do Box UV
    max_block_width = max(c['w'] for c in cubes)
    canvas_size = max(64, next_power_of_2(max_block_width))

    while True:
        pos_x, pos_y = 0, 0
        row_height = 0
        fit_all = True

        for c in cubes:
            if pos_x + c['w'] > canvas_size:
                pos_x = 0
                pos_y += row_height
                row_height = 0

            if pos_y + c['h'] > canvas_size:
                fit_all = False
                break

            c['off_x'] = pos_x
            c['off_y'] = pos_y

            pos_x += c['w']
            row_height = max(row_height, c['h'])

        if fit_all: break
        canvas_size *= 2 

    total_uv_w = canvas_size
    total_uv_h = canvas_size

    # PASSO 3: O Multiplicador ("Dobrar a resolução com base na pior face")
    multiplier = get_power_of_2_multiplier(max_required_density)
    
    img_final_w = int(total_uv_w * multiplier)
    img_final_h = int(total_uv_h * multiplier)

    if img_final_w > MAX_TEXTURE_SIZE or img_final_h > MAX_TEXTURE_SIZE:
        scale_down = MAX_TEXTURE_SIZE / max(img_final_w, img_final_h)
        multiplier = multiplier * scale_down
        img_final_w = int(total_uv_w * multiplier)
        img_final_h = int(total_uv_h * multiplier)

    print(f"[PROCESSING]")
    print(f"-> Pior Densidade Local Encontrada: {max_required_density:.2f}x")
    print(f"-> Escala (Potência de 2 Aplicada): {multiplier}x")
    print(f"-> Physical Image (HD Texture): {img_final_w}x{img_final_h}")

    new_img = Image.new("RGBA", (img_final_w, img_final_h), (0, 0, 0, 0))

    # PASSO 4: Renderização final
    for c in cubes:
        el = c['el']
        sx_uv, sy_uv, sz_uv = c['sx_uv'], c['sy_uv'], c['sz_uv']
        off_x, off_y = c['off_x'], c['off_y']

        original_faces = el.get('faces', {}).copy()

        for face_name, face_data in original_faces.items():
            if 'uv' not in face_data: continue

            old_uv = face_data['uv']
            u_min, u_max = min(old_uv[0], old_uv[2]), max(old_uv[0], old_uv[2])
            v_min, v_max = min(old_uv[1], old_uv[3]), max(old_uv[1], old_uv[3])

            left = math.floor(u_min * escala_x_orig)
            top = math.floor(v_min * escala_y_orig)
            right = math.ceil(u_max * escala_x_orig)
            bottom = math.ceil(v_max * escala_y_orig)

            if right <= left: right = left + 1
            if bottom <= top: bottom = top + 1

            left = max(0, min(left, img_orig.width - 1))
            top = max(0, min(top, img_orig.height - 1))
            right = max(left + 1, min(right, img_orig.width))
            bottom = max(top + 1, min(bottom, img_orig.height))

            crop_box = (left, top, right, bottom)
            cropped_img = img_orig.crop(crop_box)

            if old_uv[0] > old_uv[2]: cropped_img = cropped_img.transpose(Image.FLIP_LEFT_RIGHT)
            if old_uv[1] > old_uv[3]: cropped_img = cropped_img.transpose(Image.FLIP_TOP_BOTTOM)

            rot = face_data.get('rotation', 0)
            if rot == 90:    cropped_img = cropped_img.transpose(Image.ROTATE_270)
            elif rot == 180: cropped_img = cropped_img.transpose(Image.ROTATE_180)
            elif rot == 270: cropped_img = cropped_img.transpose(Image.ROTATE_90)

            if face_name in ['east', 'west']:
                cropped_img = cropped_img.transpose(Image.FLIP_LEFT_RIGHT)

            layout, universal_uv = get_layout_and_uv_coords(face_name, off_x, off_y, sx_uv, sy_uv, sz_uv)
            if not layout: continue
            lx, ly, lw_uv, lh_uv = layout 

            dest_w = max(1, round(lw_uv * multiplier))
            dest_h = max(1, round(lh_uv * multiplier))

            resample_filter = getattr(Image, 'Resampling', Image).NEAREST
            cropped_img = cropped_img.resize((dest_w, dest_h), resample_filter)
            
            paste_x = round((off_x + lx) * multiplier)
            paste_y = round((off_y + ly) * multiplier)
            
            new_img.paste(cropped_img, (paste_x, paste_y))

            el['faces'][face_name]['uv'] = universal_uv
            el['faces'][face_name]['rotation'] = 0

        el['uv_offset'] = [off_x, off_y]
        el['uv'] = [off_x, off_y]
        el['box_uv'] = True

    data['box_uv'] = True
    if 'meta' not in data: data['meta'] = {}
    data['meta']['box_uv'] = True

    if 'resolution' not in data: data['resolution'] = {}
    data['resolution']['width'] = total_uv_w
    data['resolution']['height'] = total_uv_h

    abs_path = os.path.abspath(f"{OUTPUT_NAME}.png").replace("\\", "/")

    if 'textures' in data:
        for t in data['textures']:
            t['width'] = img_final_w      
            t['height'] = img_final_h     
            t['uv_width'] = total_uv_w     
            t['uv_height'] = total_uv_h    
            t['name'] = f"{OUTPUT_NAME}.png"
            t['path'] = abs_path 
            t['relative_path'] = f"./{OUTPUT_NAME}.png"
            if 'saved_path' in t:            
                t['saved_path'] = abs_path

    new_img.save(f"{OUTPUT_NAME}.png")
    with open(f"{OUTPUT_NAME}.bbmodel", 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    print(f"\n[SUCCESS!] Files saved as: {OUTPUT_NAME}")
    print("Open the model in Blockbench (DO NOT alter the project resolution inside!).")
    
    input("\nPress ENTER to close the program...")

if __name__ == "__main__":
    convert()
