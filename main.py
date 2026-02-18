import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os

# --- CẤU HÌNH HỆ THỐNG ---
TOKEN = os.getenv("DISCORD_TOKEN")
API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_GLOBAL = "http://ha-playtogether-web.haegin.kr/api/redeem"

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db_file = "database.json"
        self.user_data_file = "users.json"
        self.load_all_data()

    def load_all_data(self):
        # Đảm bảo load dữ liệu mới nhất từ file
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                self.codes_data = json.load(f)
        else:
            self.codes_data = {"vng": [], "global": []}
            self.save_codes()
            
        if os.path.exists(self.user_data_file):
            with open(self.user_data_file, "r", encoding="utf-8") as f:
                self.users_id = json.load(f)
        else:
            self.users_id = {}

    def save_codes(self):
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.codes_data, f, ensure_ascii=False, indent=4)

    def save_user_id(self, user_id, game_id):
        self.users_id[str(user_id)] = game_id
        with open(self.user_data_file, "w", encoding="utf-8") as f:
            json.dump(self.users_id, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        self.add_view(PersistentStartView())
        await self.tree.sync()
        print(f"✅ Đã đồng bộ slash commands cho {self.user}")

bot = MyBot()

# --- MODAL: XỬ LÝ NHẬP LIỆU ---
class RedeemModal(discord.ui.Modal):
    def __init__(self, api_url, version_name, code="", saved_id="", is_manual=False):
        super().__init__(title=f"Nạp Code: {version_name}")
        self.api_url = api_url
        self.version_name = version_name
        self.is_manual = is_manual
        self.fixed_code = code

        self.uid_input = discord.ui.TextInput(
            label="ID Nhân Vật (UID)", 
            default=saved_id,
            placeholder="Nhập UID của bạn...", 
            min_length=5,
            required=True
        )
        self.add_item(self.uid_input)

        if is_manual:
            self.code_input = discord.ui.TextInput(
                label="Mã Giftcode",
                placeholder="Ví dụ: PTG2026...",
                required=True
            )
            self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        final_code = self.code_input.value.strip() if self.is_manual else self.fixed_code
        uid = self.uid_input.value.strip()
        bot.save_user_id(interaction.user.id, uid)
        
        if "vnggames.com" in self.api_url:
            payload = {"data": {"role_id": uid, "server_id": "10001", "code": final_code, "main_id": "661"}}
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://giftcode.vnggames.com",
                "Referer": "https://giftcode.vnggames.com/",
                "User-Agent": "Mozilla/5.0"
            }
        else:
            payload = {"uid": uid, "coupon": final_code, "lang": "vi"}
            headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers, timeout=15) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        error_code = data.get("error_code", 1)
                        message = data.get("message", "Thất bại")
                        if error_code == 0:
                            status_msg = f"✅ **Thành công!** Quà sẽ gửi cho ID `{uid}`."
                        else:
                            status_msg = f"❌ **Thất bại:** {message}"
                    else:
                        status_msg = f"❌ **Lỗi server:** {resp.status}"

                    await interaction.followup.send(f"{status_msg}\n• Code: `{final_code}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi kết nối: {str(e)}", ephemeral=True)

# --- UI COMPONENTS ---
class CodeSelectMenu(discord.ui.Select):
    def __init__(self, version, api_url):
        bot.load_all_data() # Load lại data mỗi khi nhấn nút để cập nhật code mới nhất
        self.api_url = api_url
        self.version_name = "VNG" if version == "vng" else "Quốc Tế"
        
        options = [discord.SelectOption(label="Nhập thủ công", value="manual", emoji="✍️")]
        available_codes = bot.codes_data.get(version, [])
        for item in reversed(available_codes[-24:]):
            options.append(discord.SelectOption(label=item['code'], description=item['desc'][:50], value=item['code']))
            
        super().__init__(placeholder=f"Chọn mã Code {self.version_name}...", options=options)

    async def callback(self, interaction: discord.Interaction):
        saved_id = bot.users_id.get(str(interaction.user.id), "")
        if self.values[0] == "manual":
            await interaction.response.send_modal(RedeemModal(self.api_url, self.version_name, saved_id=saved_id, is_manual=True))
        else:
            await interaction.response.send_modal(RedeemModal(self.api_url, self.version_name, code=self.values[0], saved_id=saved_id))

class VersionSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    @discord.ui.button(label="Bản VNG (Việt Nam)", style=discord.ButtonStyle.success, emoji="🇻🇳")
    async def vng_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(); view.add_item(CodeSelectMenu("vng", API_VNG))
        await interaction.response.edit_message(content="**Bước 2:** Chọn mã Code VNG:", view=view)
    @discord.ui.button(label="Bản Global (Quốc Tế)", style=discord.ButtonStyle.primary, emoji="🌐")
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(); view.add_item(CodeSelectMenu("global", API_GLOBAL))
        await interaction.response.edit_message(content="**Bước 2:** Chọn mã Code Quốc Tế:", view=view)

class PersistentStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Bắt đầu Nhập Code", style=discord.ButtonStyle.danger, emoji="🚀", custom_id="persistent_start")
    async def start_redeem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("**Bước 1:** Chọn phiên bản:", view=VersionSelectView(), ephemeral=True)

# --- COMMANDS ---
@bot.tree.command(name="setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(title="🎁 NHẬP GIFTCODE PLAY TOGETHER", description="Hệ thống hỗ trợ nạp code tự động.", color=discord.Color.gold())
    await interaction.channel.send(embed=embed, view=PersistentStartView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

@bot.tree.command(name="addcode")
@app_commands.describe(pb="vng hoặc global", ma="Mã code", mo_ta="Nội dung quà")
@app_commands.checks.has_permissions(administrator=True)
async def add_code(interaction: discord.Interaction, pb: str, ma: str, mo_ta: str):
    pb = pb.lower()
    if pb not in ["vng", "global"]:
        return await interaction.response.send_message("❌ Nhập 'vng' hoặc 'global'", ephemeral=True)
    bot.load_all_data()
    bot.codes_data[pb].append({"code": ma.upper(), "desc": mo_ta})
    bot.save_codes()
    await interaction.response.send_message(f"✅ Đã thêm mã `{ma.upper()}` vào bản `{pb}`", ephemeral=True)

@bot.tree.command(name="delcode", description="Xóa mã code")
@app_commands.describe(pb="vng hoặc global", ma="Mã code cần xóa")
@app_commands.checks.has_permissions(administrator=True)
async def del_code(interaction: discord.Interaction, pb: str, ma: str):
    pb = pb.lower()
    bot.load_all_data()
    if pb in bot.codes_data:
        original_count = len(bot.codes_data[pb])
        bot.codes_data[pb] = [c for c in bot.codes_data[pb] if c['code'] != ma.upper()]
        if len(bot.codes_data[pb]) < original_count:
            bot.save_codes()
            await interaction.response.send_message(f"🗑️ Đã xóa mã `{ma.upper()}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❓ Không tìm thấy mã `{ma.upper()}`", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)