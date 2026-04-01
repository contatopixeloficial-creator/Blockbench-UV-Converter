# 🧊 Blockbench Auto-Bake UV Converter (Per-Face to Box)

This tool automatically converts Blockbench models using **Per-Face UV** mapping into the **Box UV** format (Minecraft Bedrock style). It repacks your textures intelligently into a power-of-2 canvas, preserving High-Definition (HD) image quality and bypassing Blockbench's internal cache bugs.

## 🚀 Features
* **Smart Auto-Detection:** Just drop your `.bbmodel` and `.png` in the same folder. No need to rename files.
* **HD Preservation:** If your original texture is 2048x2048, the converted output will maintain that crisp resolution without breaking the Box UV mathematical grid.
* **Cache Bypass:** Generates files with unique IDs to prevent Blockbench from stubbornly reverting to old cached textures.
* **Auto-UV Exterminator:** Cleans up hidden 'Auto UV' tags that often break Box UV mappings.

## 🛠️ How to Use (For Users)

It is extremely easy and plug-and-play:
1. Create an empty folder.
2. Place the Converter executable (`.exe` or `.py`) inside it.
3. Place your model (`.bbmodel`) and your texture (`.png`) in that same folder.
4. Run the converter!

*(Note: If there are multiple models or textures in the folder, the script will process the first one it finds. Keep it to one model and one texture per folder to avoid confusion).*

## ⚠️ Important Rules (Do Not Ignore)

* **DO NOT CHANGE THE RESOLUTION IN BLOCKBENCH:** When you open your converted model, the UV grid will look small (e.g., `128x128`), but the physical texture image is actually HD (e.g., `2048x2048`). If you manually change the texture size in Blockbench's project settings, **the mapping will break**. Leave it exactly as the converter generated it.
* **File Locations:** The converted model is hardcoded to look for the new texture in the exact same folder. If you move the files around, you might need to re-link the texture once inside Blockbench.

## 💻 For Developers

Feel free to fork, modify, and improve this script! 
Dependencies required:
* `Pillow` (PIL) for image processing.

Install dependencies via:
```bash
pip install Pillow
