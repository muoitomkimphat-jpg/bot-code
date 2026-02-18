import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os

# --- CẤU HÌNH ---
TOKEN = os.getenv("DISCORD_TOKEN")
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
LIST_SERVERS = ["10001", "10002", "10003"] # Tự động dò Server

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
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

# --- LOGIC NẠP CODE (ĐÃ SỬA LỖI REGION) ---
async def redeem_vng_logic(uid, code):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": "https://giftcode.vnggames.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "x-vng-main-id": "661",
        "x-vng-region": "vn" # KHẮC PHỤC LỖI REGION
    }
    
    async with aiohttp.ClientSession() as session:
        for sv_id in LIST_SERVERS:
            payload = {"data": {"role_id": uid, "server_id": sv_id, "code": code, "main_id": "661"}}
            try:
                async with session.post(API_VNG, json=payload, headers=headers, timeout=10) as resp:
                    if resp.status != 200: continue
                    data = await resp.json()
                    err = data.get("error_code")
                    msg = data.get("message", "")
                    # Nếu thấy nhân vật (Thành công hoặc lỗi code đã dùng)
                    if err == 0 or "không tìm thấy" not in msg.lower():
                        return "✅ Thành công!" if err == 0 else f"❌ {msg}"
            except: continue
        return "❌ Không tìm thấy nhân vật trên Server 1, 2, 3."

# --- BƯỚC 4: NÚT NHẤP "NHẬP CODE" CUỐI CÙNG ---
class FinalRedeemView(discord.ui.View):
    def __init__(self, uid, code):
        super().__init__(timeout=60)
        self.uid, self.code = uid, code

    @discord.ui.button(label="Nhập CODE", style=discord.ButtonStyle.success, emoji="🚀")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await redeem_vng_logic(self.uid, self.code)
        await interaction.followup.send(f"**Kết quả:** {res}\n• Code: `{self.code}`\n• ID: `{self.uid}`", ephemeral=True)

# --- BƯỚC 3: NHẬP ID (TỰ ĐIỀN NẾU ĐÃ LƯU) ---
class IDInputModal(discord.ui.Modal, title="Xác nhận thông tin nạp"):
    uid_field = discord.ui.TextInput(label="ID Nhân vật", placeholder="Dán UID của bạn vào đây...", min_length=5)
    code_field = discord.ui.TextInput(label="Mã Code", placeholder="Nhập mã code...")

    def __init__(self, selected_code=None, saved_uid=None):
        super().__init__()
        if selected_code: self.code_field.default = selected_code
        if saved_uid: self.uid_field.default = saved_uid

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.uid_field.value
        code = self.code_field.value
        # Lưu ID lại cho lần sau
        bot.users_id[str(interaction.user.id)] = uid
        bot.save_data(bot.user_data_file, bot.users_id)
        
        embed = discord.Embed(title="Kiểm tra lại thông tin", description=f"Nhấn nút phía dưới để bắt đầu nạp mã `{code}` cho ID `{uid}`", color=0x3498db)
        await interaction.response.send_message(embed=embed, view=FinalRedeemView(uid, code), ephemeral=True)

# --- BƯỚC 2: CHỌN CODE ---
class CodeSelect(discord.ui.Select):
    def __init__(self, version):
        bot.load_all_data()
        options = [discord.SelectOption(label="Tự nhập thủ công", emoji="✍️", value="manual")]
        
        codes = bot.codes_data.get(version, [])
        for item in reversed(codes[-24:]):
            options.append(discord.SelectOption(
                label=item['code'], 
                emoji=item.get('emoji', '🎁'), 
                value=item['code']
            ))
            
        super().__init__(placeholder="Chọn mã quà tặng...", options=options)

    async def callback(self, interaction: discord.Interaction):
        saved_uid = bot.users_id.get(str(interaction.user.id))
        code = self.values[0] if self.values[0] != "manual" else None
        await interaction.response.send_modal(IDInputModal(selected_code=code, saved_uid=saved_uid))

# --- BƯỚC 1: GIAO DIỆN CHÍNH (BANNER & PHIÊN BẢN) ---
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="VNG", style=discord.ButtonStyle.secondary, emoji="🇻🇳", custom_id="btn_vng")
    async def vng_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("vng"))
        await interaction.response.send_message("🎁 **CHỌN CODE VNG**", view=view, ephemeral=True)

    @discord.ui.button(label="QUỐC TẾ", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="btn_global")
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("global"))
        await interaction.response.send_message("🎁 **CHỌN CODE QUỐC TẾ**", view=view, ephemeral=True)

# --- LỆNH SETUP ---
@bot.tree.command(name="setup", description="Thiết lập bảng nạp code")
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 NHẬP GIFTCODE PLAY TOGETHER",
        description="Hệ thống hỗ trợ nạp code tự động.\n\n**Hướng dẫn:**\n1. Chọn phiên bản Game.\n2. Chọn mã Code hoặc tự nhập.\n3. Xác nhận ID nhân vật và bấm Nạp.",
        color=0xf1c40f
    )
    # THAY LINK ẢNH BANNER CỦA BẠN VÀO ĐÂY
    embed.set_image(url="https://cdn.discordapp.com/attachments/1468688509979070565/1473672608653381654/Gemini_Generated_Image_3rtd5s3rtd5s3rtd.png?ex=69971011&is=6995be91&hm=b3a8058d1005220080de368a59e8f8fd2d2fd2116939dcc11aa2f617cad9216e&") 
    
    await interaction.channel.send(embed=embed, view=MainView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

@bot.tree.command(name="addcode", description="Thêm code vào database")
async def add_code(interaction: discord.Interaction, pb: str, ma: str, emo: str):
    pb = pb.lower()
    bot.load_all_data()
    bot.codes_data[pb].append({"code": ma.upper(), "emoji": emo})
    bot.save_data(bot.db_file, bot.codes_data)
    await interaction.response.send_message(f"✅ Đã thêm mã `{ma.upper()}` thành công!", ephemeral=True)

bot.run(TOKEN)