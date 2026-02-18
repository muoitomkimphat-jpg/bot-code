import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os

# --- CẤU HÌNH ---
TOKEN = os.getenv("DISCORD_TOKEN")
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_GLOBAL = "http://ha-playtogether-web.haegin.kr/api/redeem"
LIST_SERVERS = ["10001", "10002", "10003"] # Tự động dò server VNG

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
                return json.load(f)
        return default

    def save_data(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        self.add_view(MainView()) # Giữ nút bấm sống sau khi restart
        await self.tree.sync()

bot = MyBot()

# --- LOGIC NẠP CODE TỰ ĐỘNG ---
async def redeem_vng_logic(uid, code):
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": "https://giftcode.vnggames.com/",
        "User-Agent": "Mozilla/5.0",
        "x-vng-region": "vn",
        "x-vng-main-id": "661"
    }
    async with aiohttp.ClientSession() as session:
        for sv_id in LIST_SERVERS:
            payload = {"data": {"role_id": uid, "server_id": sv_id, "code": code, "main_id": "661"}}
            try:
                async with session.post(API_VNG, json=payload, headers=headers, timeout=10) as resp:
                    data = await resp.json()
                    err = data.get("error_code")
                    msg = data.get("message", "")
                    if err == 0 or "không tìm thấy" not in msg.lower():
                        return "✅ Thành công!" if err == 0 else f"❌ {msg}"
            except: continue
        return "❌ Không tìm thấy nhân vật."

# --- GIAO DIỆN MODAL ---
class ManualCodeModal(discord.ui.Modal, title="Tự Nhập Giftcode"):
    code = discord.ui.TextInput(label="Mã Code", placeholder="Nhập mã code tại đây...")
    def __init__(self, uid, version):
        super().__init__()
        self.uid, self.version = uid, version
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        res = await redeem_vng_logic(self.uid, self.code.value.upper())
        await interaction.followup.send(f"**Kết quả:** {res}\n• Code: `{self.code.value.upper()}`", ephemeral=True)

class UIDModal(discord.ui.Modal, title="Cập Nhật ID Nhân Vật"):
    uid = discord.ui.TextInput(label="UID (ID Nhân Vật)", placeholder="Nhập UID của bạn...", min_length=5)
    async def on_submit(self, interaction: discord.Interaction):
        bot.save_user(interaction.user.id, self.uid.value) # Cần hàm save_user cụ thể
        bot.users_id[str(interaction.user.id)] = self.uid.value
        bot.save_data(bot.user_data_file, bot.users_id)
        await interaction.response.send_message(f"✅ Đã lưu UID: `{self.uid.value}`", ephemeral=True)

# --- SELECT MENU ĐỘNG ---
class DynamicCodeSelect(discord.ui.Select):
    def __init__(self, version):
        bot.load_all_data()
        options = [discord.SelectOption(label="Tự nhập CODE", emoji="✍️", value="manual")]
        codes = bot.codes_data.get(version, [])
        
        for item in reversed(codes[-24:]):
            # Lấy emoji từ database, nếu không có thì để mặc định 🎁
            emo = item.get("emoji", "🎁")
            options.append(discord.SelectOption(label=item['code'], description=item.get('desc', ''), emoji=emo, value=item['code']))
            
        super().__init__(placeholder=f"Chọn mã Code {version.upper()}...", options=options)
        self.version = version

    async def callback(self, interaction: discord.Interaction):
        uid = bot.users_id.get(str(interaction.user.id))
        if not uid: return await interaction.response.send_message("Bạn chưa nhập ID!", ephemeral=True)
        
        if self.values[0] == "manual":
            await interaction.response.send_modal(ManualCodeModal(uid, self.version))
        else:
            await interaction.response.defer(ephemeral=True)
            res = await redeem_vng_logic(uid, self.values[0])
            await interaction.followup.send(f"**Kết quả:** {res}\n• Code: `{self.values[0]}`", ephemeral=True)

# --- VIEW CHÍNH (GIỐNG COWA) ---
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Play Together VNG", style=discord.ButtonStyle.gray, emoji="🇻🇳", custom_id="vng_btn", row=0)
    async def vng_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(DynamicCodeSelect("vng"))
        await interaction.response.send_message("🎁 **CHỌN CODE VNG**", view=view, ephemeral=True)

    @discord.ui.button(label="Play Together Global", style=discord.ButtonStyle.gray, emoji="🌐", custom_id="global_btn", row=0)
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(DynamicCodeSelect("global"))
        await interaction.response.send_message("🎁 **CHỌN CODE QUỐC TẾ**", view=view, ephemeral=True)

    @discord.ui.button(label="Tự Nhập ID", style=discord.ButtonStyle.gray, emoji="📝", custom_id="id_btn", row=1)
    async def id_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UIDModal())

# --- LỆNH QUẢN LÝ ---
@bot.tree.command(name="setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 NHẬP GIFTCODE PLAY TOGETHER", 
                          description="Hệ thống hỗ trợ nạp code tự động cho cả VNG và Quốc Tế.", 
                          color=0xADD8E6)
    embed.set_image(url="https://i.imgur.com/your_banner_link.png") # Thêm banner nếu thích
    await interaction.channel.send(embed=embed, view=MainView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

@bot.tree.command(name="addcode")
@app_commands.describe(pb="vng hoặc global", ma="Mã code", emo="Emoji (vé, kim cương...)", mo_ta="Nội dung quà")
async def add_code(interaction: discord.Interaction, pb: str, ma: str, emo: str, mo_ta: str):
    pb = pb.lower()
    bot.load_all_data()
    bot.codes_data[pb].append({"code": ma.upper(), "emoji": emo, "desc": mo_ta})
    bot.save_data(bot.db_file, bot.codes_data)
    await interaction.response.send_message(f"✅ Đã thêm mã `{ma.upper()}` với emoji {emo}", ephemeral=True)

bot.run(TOKEN)