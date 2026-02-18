import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import os
import asyncio

# --- CẤU HÌNH HỆ THỐNG ---
TOKEN = os.getenv("DISCORD_TOKEN")
# Cập nhật API VNG từ tab Network bạn đã tìm thấy
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
        if os.path.exists(self.db_file):
            with open(self.db_file, "r", encoding="utf-8") as f:
                self.codes_data = json.load(f)
        else:
            self.codes_data = {"vng": [], "global": []}
            
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
        
        # Cấu trúc Payload cập nhật cho VNG (dựa trên tab Payload của bạn)
        if "vnggames.com" in self.api_url:
            payload = {
                "data": {
                    "role_id": uid,
                    "server_id": "10001", # Thường là 10001 cho server VN
                    "code": final_code,
                    "main_id": "661"      # ID định danh game Play Together VNG
                }
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://giftcode.vnggames.com",
                "Referer": "https://giftcode.vnggames.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        else:
            # Payload cho bản Global (giữ nguyên theo cấu trúc Haegin)
            payload = {"uid": uid, "coupon": final_code, "lang": "vi"}
            headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Kiểm tra logic phản hồi của VNG (thường dùng error_code)
                        error_code = data.get("error_code")
                        message = data.get("message", "Không có phản hồi từ hệ thống")
                        
                        if error_code == 0:
                            status_msg = f"✅ **Thành công!** Quà sẽ gửi vào thư game cho ID `{uid}`."
                        else:
                            status_msg = f"❌ **Thất bại:** {message}"
                    else:
                        status_msg = f"❌ **Lỗi server:** Mã lỗi {resp.status}. Có thể API bị thay đổi."

                    await interaction.followup.send(
                        f"{status_msg}\n\n• Code: `{final_code}`\n• Phiên bản: `{self.version_name}`", 
                        ephemeral=True
                    )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi kết nối server game: {str(e)}", ephemeral=True)

# --- UI COMPONENTS: CHỌN CODE ---
class CodeSelectMenu(discord.ui.Select):
    def __init__(self, version, api_url):
        self.api_url = api_url
        self.version_name = "VNG" if version == "vng" else "Quốc Tế"
        
        options = [discord.SelectOption(label="Nhập thủ công", value="manual", emoji="✍️", description="Tự nhập mã code của bạn")]
        available_codes = bot.codes_data.get(version, [])[-24:]
        for item in reversed(available_codes):
            options.append(discord.SelectOption(
                label=item['code'], 
                description=item['desc'][:50],
                value=item['code']
            ))
        super().__init__(placeholder=f"Chọn mã Code {self.version_name}...", options=options)

    async def callback(self, interaction: discord.Interaction):
        saved_id = bot.users_id.get(str(interaction.user.id), "")
        selected = self.values[0]
        if selected == "manual":
            await interaction.response.send_modal(RedeemModal(self.api_url, self.version_name, saved_id=saved_id, is_manual=True))
        else:
            await interaction.response.send_modal(RedeemModal(self.api_url, self.version_name, code=selected, saved_id=saved_id))

class VersionSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    @discord.ui.button(label="Bản VNG (Việt Nam)", style=discord.ButtonStyle.success, emoji="🇻🇳")
    async def vng_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(); view.add_item(CodeSelectMenu("vng", API_VNG))
        await interaction.response.edit_message(content="**Bước 2:** Chọn mã Code từ danh sách bên dưới:", view=view)
    @discord.ui.button(label="Bản Global (Quốc Tế)", style=discord.ButtonStyle.primary, emoji="🌐")
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(); view.add_item(CodeSelectMenu("global", API_GLOBAL))
        await interaction.response.edit_message(content="**Bước 2:** Chọn mã Code từ danh sách bên dưới:", view=view)

class PersistentStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Bắt đầu Nhập Code", style=discord.ButtonStyle.danger, emoji="🚀", custom_id="persistent_start")
    async def start_redeem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("**Bước 1:** Chọn phiên bản Play Together:", view=VersionSelectView(), ephemeral=True)

@bot.tree.command(name="setup", description="Gửi bảng nạp code vào kênh (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎁 NHẬP GIFTCODE PLAY TOGETHER",
        description="Tiện ích hỗ trợ nhập mã quà tặng nhanh chóng.\n\n**✨ Tính năng:**\n• Hỗ trợ VNG & Global.\n• Tự lưu ID nhân vật.\n• Cập nhật code mới nhất.",
        color=discord.Color.from_rgb(255, 204, 0)
    )
    await interaction.channel.send(embed=embed, view=PersistentStartView())
    await interaction.response.send_message("✅ Đã thiết lập!", ephemeral=True)

@bot.tree.command(name="addcode", description="Thêm code mới (Admin)")
@app_commands.describe(pb="vng hoặc global", ma="Mã code", mo_ta="Nội dung quà")
@app_commands.checks.has_permissions(administrator=True)
async def add_code(interaction: discord.Interaction, pb: str, ma: str, mo_ta: str):
    pb = pb.lower()
    if pb not in ["vng", "global"]:
        return await interaction.response.send_message("❌ Sai phiên bản!", ephemeral=True)
    bot.codes_data[pb].append({"code": ma.upper(), "desc": mo_ta})
    bot.save_codes()
    await interaction.response.send_message(f"✅ Đã thêm Code: `{ma.upper()}`", ephemeral=True)

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ LỖI: Thiếu DISCORD_TOKEN!")