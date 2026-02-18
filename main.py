import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os

# --- CẤU HÌNH ---
# BẮT BUỘC: Thay TOKEN mới vào đây, Token hiện tại của bạn đang bị lỗi LoginFailure
TOKEN = "GIAO_DIEN_MOI_LAY_TOKEN_TAI_DAY" 

# Cập nhật API Endpoint chuẩn để tránh lỗi 404
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"

# Server 2 của bạn là 80002
LIST_SERVERS = ["80002", "80001", "10001"]

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db_file = "database.json"
        self.user_data_file = "users.json"
        self.load_all_data()

    def load_all_data(self):
        self.codes_data = self.read_json(self.db_file, {"vng": [], "global": []})
        self.users_id = self.read_json(self.user_data_file, {})

    def read_json(self, file, default):
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                try: return json.load(f)
                except: return default
        return default

    def save_data(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        self.add_view(MainView())
        await self.tree.sync()

bot = MyBot()

# --- LOGIC NẠP CODE ĐÃ FIX LỖI 404 & REGION ---
async def redeem_vng_logic(uid, code):
    # Header lấy chính xác từ Screenshot 2026-02-18 210644.png của bạn
    headers = {
        "authority": "vgrapi-sea.vnggames.com",
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://giftcode.vnggames.com",
        "referer": "https://giftcode.vnggames.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "x-client-region": "vn",
        "x-vng-main-id": "661",
        "x-vng-region": "vn"
    }
    
    async with aiohttp.ClientSession() as session:
        for sv_id in LIST_SERVERS:
            # Payload gửi kèm lang=vi để khớp với web
            payload = {
                "data": {
                    "role_id": str(uid).strip(), 
                    "server_id": sv_id, 
                    "code": str(code).strip(), 
                    "main_id": "661"
                }
            }
            try:
                # Thêm tham số lang=vi vào URL để tránh 404 tùy server
                url_with_lang = f"{API_VNG}?lang=vi"
                async with session.post(url_with_lang, json=payload, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        print(f"DEBUG: Server {sv_id} lỗi HTTP {resp.status}")
                        continue
                    
                    data = await resp.json()
                    msg = data.get("message", "")
                    print(f"Server {sv_id} phản hồi: {msg}")

                    if "không tìm thấy" not in msg.lower():
                        if data.get("error_code") == 0:
                            return f"✅ **Thành công!** (Nhân vật tại Server {sv_id})"
                        return f"❌ {msg}"
            except: continue
        return "❌ Vẫn không tìm thấy nhân vật. Hãy chắc chắn bạn dùng UID `NK5X-DUHL-LMGC`."

# --- GIAO DIỆN MODAL ---
class IDModal(discord.ui.Modal, title="Nạp Code Play Together"):
    uid_input = discord.ui.TextInput(label="ID (UID)", default="NK5X-DUHL-LMGC")
    code_input = discord.ui.TextInput(label="Mã Code", placeholder="Nhập Giftcode...")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        res = await redeem_vng_logic(self.uid_input.value, self.code_input.value)
        await interaction.followup.send(f"**Kết quả:** {res}", ephemeral=True)

class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="NẠP CODE VNG", style=discord.ButtonStyle.danger, custom_id="vng_btn")
    async def vng(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IDModal())

@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    await interaction.channel.send("🚀 Nhấn để nạp code!", view=MainView())
    await interaction.response.send_message("Xong!", ephemeral=True)

bot.run(TOKEN)