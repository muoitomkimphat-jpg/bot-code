import discord
from discord.ext import commands
import aiohttp
import json
import os
import asyncio

# ================= CONFIG =================

TOKEN = os.getenv("DISCORD_TOKEN")  # KHÔNG ghi token trực tiếp

if not TOKEN:
    raise ValueError("❌ Chưa thiết lập DISCORD_TOKEN trong biến môi trường!")

API_VNG = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem?lang=vi"

LIST_SERVERS = ["80002", "80001", "10001"]

# ================= BOT CLASS =================

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
                try:
                    return json.load(f)
                except:
                    return default
        return default

    def save_json(self, file, data):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def setup_hook(self):
        self.add_view(MainView())
        await self.tree.sync()
        print("✅ Bot đã sync slash command!")

bot = MyBot()

# ================= LOGIC NẠP CODE =================

async def redeem_vng_logic(uid, code):
    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://giftcode.vnggames.com",
        "referer": "https://giftcode.vnggames.com/",
        "user-agent": "Mozilla/5.0",
        "x-client-region": "vn",
        "x-vng-main-id": "661",
        "x-vng-region": "vn"
    }

    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for server_id in LIST_SERVERS:

            payload = {
                "data": {
                    "role_id": str(uid).strip(),
                    "server_id": server_id,
                    "code": str(code).strip(),
                    "main_id": "661"
                }
            }

            try:
                async with session.post(API_VNG, json=payload, headers=headers) as resp:

                    if resp.status != 200:
                        continue

                    data = await resp.json()
                    message = data.get("message", "")

                    print(f"[DEBUG] Server {server_id}: {message}")

                    if data.get("error_code") == 0:
                        return f"✅ Thành công tại server {server_id}"

                    if "không tìm thấy" not in message.lower():
                        return f"❌ {message}"

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print("Lỗi:", e)
                continue

    return "❌ Không tìm thấy nhân vật hoặc code sai."

# ================= MODAL =================

class IDModal(discord.ui.Modal, title="Nạp Code Play Together"):

    uid_input = discord.ui.TextInput(
        label="ID (UID)",
        placeholder="Ví dụ: NK5X-DUHL-LMGC",
        required=True
    )

    code_input = discord.ui.TextInput(
        label="Mã Giftcode",
        placeholder="Nhập code...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        result = await redeem_vng_logic(
            self.uid_input.value,
            self.code_input.value
        )

        await interaction.followup.send(
            f"**Kết quả:** {result}",
            ephemeral=True
        )

# ================= VIEW =================

class MainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="NẠP CODE VNG",
        style=discord.ButtonStyle.danger,
        custom_id="vng_btn"
    )
    async def vng_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(IDModal())

# ================= SLASH COMMAND =================

@bot.tree.command(name="setup", description="Tạo nút nạp code")
async def setup_command(interaction: discord.Interaction):
    await interaction.channel.send(
        "🚀 Nhấn nút bên dưới để nạp code:",
        view=MainView()
    )
    await interaction.response.send_message("✅ Đã tạo nút!", ephemeral=True)

# ================= READY EVENT =================

@bot.event
async def on_ready():
    print(f"🔥 Bot đã online: {bot.user}")

# ================= RUN =================

bot.run(TOKEN)
