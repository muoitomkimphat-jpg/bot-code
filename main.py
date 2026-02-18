import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os

# --- CẤU HÌNH ---
TOKEN = "YOUR_BOT_TOKEN_HERE"
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"

# Server 2 của bạn có mã định danh là 80002
LIST_SERVERS = ["80002", "80001", "10001", "10002"]

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

# --- LOGIC NẠP CODE "CHẮC ĂN" ---
async def redeem_vng_logic(uid, code):
    # Header mô phỏng chính xác từ Screenshot 2026-02-18 210644.png của bạn
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
            # Gửi UID chính xác như NK5X-DUHL-LMGC
            payload = {
                "data": {
                    "role_id": str(uid).strip(), 
                    "server_id": sv_id, 
                    "code": str(code).strip(), 
                    "main_id": "661"
                }
            }
            try:
                async with session.post(API_VNG, json=payload, headers=headers, timeout=10) as resp:
                    # Nếu báo 404, có thể server ID đó không đúng, bot sẽ thử mã tiếp theo
                    if resp.status == 404: continue 
                    
                    data = await resp.json()
                    msg = data.get("message", "")
                    
                    # Log để bạn xem trong Terminal của bot
                    print(f"Thử Server {sv_id} cho UID {uid}: {msg}")

                    if "không tìm thấy" not in msg.lower():
                        if data.get("error_code") == 0:
                            return f"✅ **Thành công!** (Hệ thống tìm thấy bạn tại Server {sv_id})"
                        return f"❌ {msg}"
            except Exception as e:
                print(f"Lỗi kết nối: {e}")
                continue
                
        return "❌ **Thất bại:** Hệ thống VNG vẫn báo không tìm thấy nhân vật này trên Server 1 & 2."

# --- GIAO DIỆN MODAL (TỰ ĐIỀN UID CỦA BẠN) ---
class IDModal(discord.ui.Modal, title="Nạp Giftcode Play Together"):
    uid_input = discord.ui.TextInput(
        label="ID Nhân vật (UID)", 
        default="NK5X-DUHL-LMGC", # Đã điền sẵn UID của bạn để test
        placeholder="Ví dụ: NK5X-DUHL-LMGC"
    )
    code_input = discord.ui.TextInput(label="Mã Giftcode", placeholder="Nhập mã code cần nạp...")

    def __init__(self, code=None, uid=None):
        super().__init__()
        if code: self.code_input.default = code
        if uid: self.uid_input.default = uid

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.uid_input.value.strip()
        code = self.code_input.value.strip().upper()
        
        # Lưu UID cho lần sau
        bot.users_id[str(interaction.user.id)] = uid
        bot.save_data(bot.user_data_file, bot.users_id)
        
        await interaction.response.defer(ephemeral=True)
        res = await redeem_vng_logic(uid, code)
        
        embed = discord.Embed(
            title="Kết quả nạp code",
            description=f"**Trạng thái:** {res}\n**UID:** `{uid}`\n**Code:** `{code}`",
            color=0x2ecc71 if "Thành công" in res else 0xe74c3c
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

# (Các phần MainView và Select giữ nguyên như các bản trước)
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="NẠP CODE VNG", style=discord.ButtonStyle.danger, emoji="🇻🇳", custom_id="vng_btn")
    async def vng(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IDModal(uid=bot.users_id.get(str(interaction.user.id))))

@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(title="🚀 HỆ THỐNG NẠP CODE", color=0x3498db)
    embed.set_image(url="https://i.imgur.com/vHlyuWf.png") # Banner bạn thích
    await interaction.channel.send(embed=embed, view=MainView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

bot.run(TOKEN)