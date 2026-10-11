import os
import io
import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import datetime
import random
import asyncio

# Lista zakazanych słów (wulgaryzmów) - możesz dopisać własne
BAD_WORDS = ["debil", "idiota", "frajer", "chuj", "kurwa", "pizda", "jebac", "suka"]

# Konfiguracja bota i uprawnień (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user.name}!")
    print("🤖 Bot Discord Marketplace działa i chroni serwer!")

# ==========================================
# 🚪 SYSTEM POWITAŃ
# ==========================================
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="powitania")
    if channel:
        embed = discord.Embed(
            title="👋 Nowy członek serwera!",
            description=f"Witaj {member.mention}!\nCieszymy się, że jesteś z nami. \n\n📊 Jest nas już: **{member.guild.member_count}**",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await channel.send(embed=embed)

# ==========================================
# 🔐 SYSTEM WERYFIKACJI
# ==========================================
class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zweryfikuj się", style=discord.ButtonStyle.green, custom_id="verify_btn", emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        role_name = "Klient"
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        
        if role:
            if role in interaction.user.roles:
                await interaction.response.send_message("👉 Jesteś już zweryfikowany!", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"🎉 Pomyślnie zweryfikowano! Nadano rolę **{role_name}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Błąd: Nie znaleziono na serwerze roli o nazwie `{role_name}`. Stwórz ją!", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_weryfikacja(ctx):
    embed = discord.Embed(
        title="🔐 STREFA WERYFIKACJI",
        description="Kliknij poniższy przycisk, aby potwierdzić, że jesteś człowiekiem, odblokować dostęp do serwera i otrzymać rolę **Klient**.",
        color=discord.Color.green()
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Discord Marketplace • Bezpieczeństwo przede wszystkim")
    
    view = VerificationView()
    await ctx.send(embed=embed, view=view)

# ==========================================
# 🎟️ SYSTEM TICKETÓW + OKIENKO FINANSOWE
# ==========================================
class TicketFinancesModal(Modal):
    """Okienko wyskakujące przy zamykaniu ticketu"""
    kwota = TextInput(label="Kwota transakcji", placeholder="np. 150 PLN lub 0 PLN / Brak", required=True)
    metoda = TextInput(label="Metoda płatności", placeholder="np. BLIK, PayPal, PSC lub Brak", required=True)

    def __init__(self, creator_id, claimed_by, channel_history, channel_name):
        super().__init__(title="Podsumowanie finansowe ticketu")
        self.creator_id = creator_id
        self.claimed_by = claimed_by
        self.channel_history = channel_history
        self.channel_name = channel_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("💾 Zapisywanie danych i zamykanie kanału...", ephemeral=True)
        
        # 1. Generowanie transkrypcji (tekstu z całej rozmowy)
        log_content = f"--- TRANSKRYPCJA ZGŁOSZENIA {self.channel_name} ---\n"
        log_content += f"Rozliczenie: {self.kwota.value} przez {self.metoda.value}\n"
        log_content += f"Przejął: {self.claimed_by}\n\n"
        
        for msg in self.channel_history:
            log_content += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.content}\n"
            
        file_data = io.BytesIO(log_content.encode('utf-8'))
        
        # Sprawdzamy czy transakcja to 0 PLN / anulowana
        kwota_clean = self.kwota.value.lower().strip()
        is_zero_or_failed = "0" in kwota_clean or "brak" in kwota_clean or "nie" in kwota_clean

        # 2. Wysyłanie raportu na prywatny kanał właściciela (#transakcje)
        transakcje_channel = discord.utils.get(interaction.guild.text_channels, name="transakcje")
        if transakcje_channel:
            # Ustalamy kolor i tekst w zależności od tego czy transakcja się udała
            if is_zero_or_failed:
                title_text = "⚠️ ANULOWANA TRANSAKCJA LUB 0 PLN (KONTROLA)"
                embed_color = discord.Color.red()
                # Oznaczamy właściciela korporacji/serwera jeśli transakcja to 0 PLN (zabezpieczenie przed oszustwem)
                mention_text = f"📢 @everyone - Wykryto zamknięcie ticketu z kwotą **0 PLN / Brak**! Sprawdź logi rozmowy poniżej."
            else:
                title_text = "💰 NOWE ROZLICZENIE TRANSAKCJI"
                embed_color = discord.Color.gold()
                mention_text = ""

            embed_report = discord.Embed(
                title=title_text,
                color=embed_color,
                timestamp=datetime.datetime.utcnow()
            )
            embed_report.add_field(name="🎟️ Nazwa ticketu", value=f"`{self.channel_name}`", inline=True)
            embed_report.add_field(name="👤 Klient (ID)", value=f"<@{self.creator_id}> (`{self.creator_id}`)", inline=True)
            embed_report.add_field(name="🤠 Zamknął / Przejął", value=f"{self.claimed_by.mention if self.claimed_by else 'Brak'}", inline=True)
            embed_report.add_field(name="💵 Kwota", value=f"**{self.kwota.value}**", inline=True)
            embed_report.add_field(name="💳 Płatność", value=f"**{self.metoda.value}**", inline=True)
            
            if interaction.guild.icon:
                embed_report.set_thumbnail(url=interaction.guild.icon.url)
                
            discord_file_owner = discord.File(io.BytesIO(log_content.encode('utf-8')), filename=f"log-{self.channel_name}.txt")
            await transakcje_channel.send(content=mention_text, embed=embed_report, file=discord_file_owner)

        # 3. Wysyłanie kopii do Klienta na DM (zawsze dostaje kopię rozmowy dla bezpieczeństwa)
        creator = interaction.guild.get_member(self.creator_id)
        if creator:
            try:
                discord_file_client = discord.File(io.BytesIO(log_content.encode('utf-8')), filename=f"log-{self.channel_name}.txt")
                await creator.send(
                    content=f"🔒 Twój ticket `{self.channel_name}` na serwerze **{interaction.guild.name}** został zamknięty. W załączniku przesyłamy pełny zapis rozmowy.",
                    file=discord_file_client
                )
            except discord.Forbidden:
                pass

        # 4. Usunięcie kanału ticketu po zapisaniu wszystkiego
        await interaction.channel.delete()

class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Pomoc", emoji="❓"),
            discord.SelectOption(label="Pytanie", emoji="💬"),
            discord.SelectOption(label="Zakup", emoji="🛒"),
            discord.SelectOption(label="Błąd", emoji="⚙️"),
            discord.SelectOption(label="Oszustwo / Middleman", emoji="🤝"),
            discord.SelectOption(label="Ranga", emoji="👑"),
        ]
        super().__init__(placeholder="Wybierz powód zgłoszenia...", min_values=1, max_values=1, options=options, custom_id="ticket_select")

    async def callback(self, interaction: discord.Interaction):
        reason = self.values[0]
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel_name = f"ticket-{reason.lower().replace(' / ', '-')}-{user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Stworzono zgłoszenie: {ticket_channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title=f"🎟️ Zgłoszenie: {reason}",
            description=f"Witaj {user.mention}, opisz tutaj dokładnie swój problem. Administracja zaraz się Tobą zajmie.",
            color=discord.Color.purple()
        )
        
        if "Oszustwo" in reason:
            embed.add_field(
                name="🤝 SYSTEM MIDDLEMAN (Pośrednik)", 
                value="Pamiętaj! Korzystanie z naszego Middlemana jest w 100% darmowe. Chroni Cię to przed oszustwem. Nigdy nie przekazuj pieniędzy ani plików bezpośrednio sprzedawcy przed zatwierdzeniem transakcji przez naszą kadrę!",
                inline=False
            )

        view = TicketControlView(user.id)
        await ticket_channel.send(embed=embed, view=view)

class TicketControlView(View):
    def __init__(self, creator_id):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.claimed_by = None

    @discord.ui.button(label="Przejmij (Claim)", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def claim_btn(self, interaction: discord.Interaction, button: Button):
        self.claimed_by = interaction.user
