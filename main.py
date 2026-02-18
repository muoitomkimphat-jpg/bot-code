import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
import asyncio

# --- CẤU HÌNH ---
TOKEN = os.getenv("DISCORD_TOKEN") or "YOUR_TOKEN_HERE"
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"

# Danh sách Server ID phổ biến (Play Together VNG)
# Thử các cụm 8000x và 1000x
LIST_SERVERS = ["80002", "80001", "10001", "10002", "1001"] 

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
            try:
                with open(file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return default
        return default

    def save_data(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        # Đăng ký View để các nút bấm hoạt động sau khi bot restart
        self.add_view(MainView())
        await self.tree.sync()

bot = MyBot()

# --- LOGIC NẠP CODE TỐI ƯU ---
async def redeem_vng_logic(uid, code):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": "https://giftcode.vnggames.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "x-vng-main-id": "661",
        "x-vng-region": "vn"
    }
    
    async with aiohttp.ClientSession() as session:
        for sv_id in LIST_SERVERS:
            payload = {
                "data": {
                    "role_id": str(uid).strip(), 
                    "server_id": str(sv_id), 
                    "code": str(code).strip(), 
                    "main_id": "661"
                }
            }
            try:
                async with session.post(API_VNG, json=payload, headers=headers, timeout=10) as resp:
                    if resp.status != 200: continue
                    
                    data = await resp.json()
                    err = data.get("error_code")
                    msg = data.get("message", "")
                    
                    # Nếu thành công
                    if err == 0:
                        return f"✅ **Thành công!** (Server {sv_id})"
                    
                    # Nếu lỗi là do không tìm thấy nhân vật, tiếp tục thử server khác
                    # Mã lỗi phổ biến của VNG cho Role không tồn tại là -20002
                    if err in [-20001, -20002] or "không tìm thấy" in msg.lower():
                        continue
                        
                    # Nếu lỗi khác (Code hết hạn, đã dùng, sai code) -> Trả về lỗi luôn
                    return f"❌ {msg}"
            except Exception as e:
                print(f"Lỗi kết nối {sv_id}: {e}")
                continue
                
        return "❌ **Lỗi:** Không tìm thấy nhân vật trên toàn bộ Server. Vui lòng kiểm tra lại UID!"

# --- GIAO DIỆN XÁC NHẬN ---
class FinalView(discord.ui.View):
    def __init__(self, uid, code):
        super().__init__(timeout=120)
        self.uid, self.code = uid, code

    @discord.ui.button(label="Nhập CODE", style=discord.ButtonStyle.success, emoji="🚀")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Chặn bấm nhiều lần
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Gọi logic nạp
        res = await redeem_vng_logic(self.uid, self.code)
        
        # Cập nhật kết quả cuối cùng vào chính tin nhắn đó
        embed = discord.Embed(
            title="Kết quả nạp Code",
            description=f"**Trạng thái:** {res}\n**UID:** `{self.uid}`\n**Mã:** `{self.code}`",
            color=0x2ecc71 if "Thành công" in res else 0xe74c3c
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

# --- MODAL NHẬP THÔNG TIN ---
class IDModal(discord.ui.Modal, title="Thông Tin Nạp Code"):
    uid_input = discord.ui.TextInput(label="ID Nhân vật (UID)", placeholder="Nhập UID của bạn...", min_length=5)
    code_input = discord.ui.TextInput(label="Mã Code", placeholder="Nhập Giftcode tại đây...", min_length=3)

    def __init__(self, code=None, uid=None):
        super().__init__()
        if code: self.code_input.default = code
        if uid: self.uid_input.default = uid

    async def on_submit(self, interaction: discord.Interaction):
        uid, code = self.uid_input.value, self.code_input.value
        # Lưu UID vào data
        bot.users_id[str(interaction.user.id)] = uid
        bot.save_data(bot.user_data_file, bot.users_id)
        
        embed = discord.Embed(
            title="Xác nhận thông tin",
            description=f"Bạn muốn nạp mã `{code}` cho tài khoản `{uid}`?\n\n*Lưu ý: Hệ thống sẽ tự dò tìm Server phù hợp.*",
            color=0xf1c40f
        )
        await interaction.response.send_message(embed=embed, view=FinalView(uid, code), ephemeral=True)

# --- CHỌN CODE ---
class CodeSelect(discord.ui.Select):
    def __init__(self, version):
        bot.load_all_data()
        options = [discord.SelectOption(label="Tự nhập thủ công", emoji="✍️", value="manual")]
        codes = bot.codes_data.get(version, [])
        # Lấy 24 code mới nhất
        for item in reversed(codes[-24:]):
            options.append(discord.SelectOption(label=item['code'], emoji=item.get('emoji', '🎁'), value=item['code']))
            
        super().__init__(placeholder="Chọn mã Code có sẵn...", options=options)
        self.version = version

    async def callback(self, interaction: discord.Interaction):
        uid = bot.users_id.get(str(interaction.user.id))
        val = self.values[0]
        code = val if val != "manual" else None
        await interaction.response.send_modal(IDModal(code=code, uid=uid))

# --- VIEW CHÍNH ---
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="VNG", style=discord.ButtonStyle.danger, emoji="🇻🇳", custom_id="vng_btn")
    async def vng(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("vng"))
        await interaction.response.send_message("👉 **Bước 2: Chọn Code VNG**", view=view, ephemeral=True)

    @discord.ui.button(label="QUỐC TẾ", style=discord.ButtonStyle.primary, emoji="🌐", custom_id="global_btn")
    async def glob(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("global"))
        await interaction.response.send_message("👉 **Bước 2: Chọn Code Quốc Tế**", view=view, ephemeral=True)

# --- COMMANDS ---
@bot.tree.command(name="setup", description="Thiết lập tin nhắn nạp code")
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 HỆ THỐNG NẠP CODE TỰ ĐỘNG", 
        description="Vui lòng nhấn vào nút bên dưới để chọn phiên bản game bạn đang chơi.", 
        color=0x3498db
    )
    embed.set_image(url="https://media.discordapp.net/attachments/1468688509979070565/1473672608653381654/Gemini_Generated_Image_3rtd5s3rtd5s3rtd.png") 
    embed.set_footer(text="Hệ thống tự động dò tìm Server nhân vật")
    
    await interaction.channel.send(embed=embed, view=MainView())
    await interaction.response.send_message("✅ Đã thiết lập bảng nạp code!", ephemeral=True)

@bot.tree.command(name="addcode", description="Thêm code mới vào danh sách")
@app_commands.choices(pb=[
    app_commands.Choice(name="VNG", value="vng"),
    app_commands.Choice(name="Quốc Tế", value="global")
])
async def add_code(interaction: discord.Interaction, pb: str, ma: str, emo: str = "🎁"):
    bot.load_all_data()
    bot.codes_data[pb].append({"code": ma.upper(), "emoji": emo})
    bot.save_data(bot.db_file, bot.codes_data)
    await interaction.response.send_message(f"✅ Đã thêm mã `{ma.upper()}` vào danh sách {pb.upper()}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot đã sẵn sàng: {bot.user.name}")

bot.run(TOKEN)