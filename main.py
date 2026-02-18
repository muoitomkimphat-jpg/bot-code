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
LIST_SERVERS = ["10001", "10002", "10003"]

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.db_file = "database.json"
        self.user_data_file = "users.json"
        self.load_all_data()

    def load_all_data(self):
        # Load database code
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                self.codes_data = json.load(f)
        else:
            self.codes_data = {"vng": [], "global": []}
            
        # Load database người dùng
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, "r", encoding="utf-8") as f:
                self.users_id = json.load(f)
        else:
            self.users_id = {}

    def save_user(self, user_id, game_id):
        self.users_id[str(user_id)] = game_id
        with open(self.user_data_file, "w", encoding="utf-8") as f:
            json.dump(self.users_id, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        self.add_view(MainView())
        await self.tree.sync()

bot = MyBot()

# --- LOGIC NẠP CODE TỰ ĐỘNG ---
async def redeem_logic(version, uid, code):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": "https://giftcode.vnggames.com/",
        "x-vng-region": "vn",
        "x-vng-main-id": "661"
    }
    async with aiohttp.ClientSession() as session:
        if version == "vng":
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
        else:
            # Logic cho bản Quốc tế (Global)
            payload = {"uid": uid, "coupon": code}
            async with session.post(API_GLOBAL, json=payload) as resp:
                return "✅ Thành công!" if resp.status == 200 else "❌ Lỗi kết nối Global."

# --- MODAL NHẬP ID VÀ XÁC NHẬN ---
class FinalStepView(discord.ui.View):
    def __init__(self, version, code, uid):
        super().__init__(timeout=60)
        self.version = version
        self.code = code
        self.uid = uid

    @discord.ui.button(label="Nhập CODE", style=discord.ButtonStyle.success, emoji="🚀")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        res = await redeem_logic(self.version, self.uid, self.code)
        await interaction.followup.send(f"**Kết quả:** {res}\n• ID: `{self.uid}`\n• Code: `{self.code}`", ephemeral=True)

class ManualEntryModal(discord.ui.Modal, title="Nhập thông tin nạp Code"):
    uid_input = discord.ui.TextInput(label="ID Nhân vật", placeholder="Nhập UID của bạn...", min_length=5)
    code_input = discord.ui.TextInput(label="Mã Code", placeholder="Nhập mã quà tặng...", required=False)

    def __init__(self, version, pre_code=None, saved_uid=None):
        super().__init__()
        self.version = version
        if pre_code: 
            self.code_input.default = pre_code
            self.code_input.label = "Mã Code (Đã chọn)"
        if saved_uid:
            self.uid_input.default = saved_uid

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.uid_input.value
        code = self.code_input.value or "Chưa nhập"
        bot.save_user(interaction.user.id, uid)
        
        embed = discord.Embed(title="Xác nhận thông tin", color=discord.Color.blue())
        embed.add_field(name="ID Nhân vật", value=f"`{uid}`", inline=True)
        embed.add_field(name="Mã Code", value=f"`{code}`", inline=True)
        
        await interaction.response.send_message(embed=embed, view=FinalStepView(self.version, code, uid), ephemeral=True)

# --- SELECT MENU CHỌN CODE ---
class CodeSelect(discord.ui.Select):
    def __init__(self, version):
        bot.load_all_data()
        options = [discord.SelectOption(label="Tự nhập thủ công", emoji="✍️", value="manual")]
        
        codes = bot.codes_data.get(version, [])
        for item in reversed(codes[-24:]):
            emo = item.get("emoji", "🎁")
            options.append(discord.SelectOption(label=item['code'], description=item.get('desc', ''), emoji=emo, value=item['code']))
            
        super().__init__(placeholder="Chọn mã Code từ danh sách...", options=options)
        self.version = version

    async def callback(self, interaction: discord.Interaction):
        saved_uid = bot.users_id.get(str(interaction.user.id))
        selected_code = self.values[0]
        
        if selected_code == "manual":
            await interaction.response.send_modal(ManualEntryModal(self.version, saved_uid=saved_uid))
        else:
            # Nếu đã chọn code có sẵn, hiện Modal để xác nhận/nhập UID
            await interaction.response.send_modal(ManualEntryModal(self.version, pre_code=selected_code, saved_uid=saved_uid))

# --- VIEW CHÍNH ---
class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="VNG", style=discord.ButtonStyle.danger, emoji="🇻🇳", custom_id="vng_btn")
    async def vng_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("vng"))
        await interaction.response.send_message("✨ **Bước 2: Chọn mã Code VNG**", view=view, ephemeral=True)

    @discord.ui.button(label="QUỐC TẾ", style=discord.ButtonStyle.primary, emoji="🌐", custom_id="global_btn")
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View().add_item(CodeSelect("global"))
        await interaction.response.send_message("✨ **Bước 2: Chọn mã Code Quốc Tế**", view=view, ephemeral=True)

# --- COMMANDS ---
@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 CODE Tự Động",
        description="Chào mừng bạn! Vui lòng chọn phiên bản game để tiếp tục.",
        color=0x2f3136
    )
    await interaction.channel.send(embed=embed, view=MainView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

@bot.tree.command(name="addcode")
async def add_code(interaction: discord.Interaction, pb: str, ma: str, emo: str, mo_ta: str):
    pb = pb.lower()
    bot.load_all_data()
    bot.codes_data[pb].append({"code": ma.upper(), "emoji": emo, "desc": mo_ta})
    bot.save_data(bot.db_file, bot.codes_data)
    await interaction.response.send_message(f"✅ Đã thêm mã `{ma.upper()}`", ephemeral=True)

bot.run(TOKEN)