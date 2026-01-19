import os
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN não encontrado nos Secrets do Replit")

MIN_GRID = 10
MAX_WORDS = 5
MOEDAS_POR_PALAVRA = 50
PREMIO_FINAL = 200
LETRA_OCULTA = "⬜"
ESPACO_VAZIO = "·"
LINHAS_EMOJI = ["🟦", "🟩", "🟪", "🟨", "🟧", "🟥"]
# =========================================

jogos = {}
usuarios_moedas = {}  # user_id -> moedas
usuarios_nome = {}    # user_id -> nome

# ---------- UTIL ----------
def carregar_palavras():
    palavras = []
    try:
        with open("palavras.txt", "r", encoding="utf-8") as f:
            for linha in f:
                p = linha.strip().upper()
                if p:
                    palavras.append(p)
    except FileNotFoundError:
        print("❌ Arquivo palavras.txt não encontrado!")
    return palavras

def criar_tabuleiro(palavras):
    grid_size = max(MIN_GRID, max(len(p) for p in palavras) + 2)
    tab = [[ESPACO_VAZIO for _ in range(grid_size)] for _ in range(grid_size)]
    palavras_info = []

    for palavra in palavras:
        for _ in range(100):
            orientacao = random.choice(["H", "V"])
            if orientacao == "H":
                linha = random.randint(0, grid_size - 1)
                col = random.randint(0, grid_size - len(palavra))
            else:
                linha = random.randint(0, grid_size - len(palavra))
                col = random.randint(0, grid_size - 1)

            cabe = True
            for i, letra in enumerate(palavra):
                r, c = (linha, col + i) if orientacao == "H" else (linha + i, col)
                if tab[r][c] != ESPACO_VAZIO and tab[r][c] != letra:
                    cabe = False
                    break
            if not cabe:
                continue

            coords = []
            for i, letra in enumerate(palavra):
                r, c = (linha, col + i) if orientacao == "H" else (linha + i, col)
                tab[r][c] = letra
                coords.append((r, c))
            palavras_info.append({"palavra": palavra, "coords": coords})
            break

    return tab, palavras_info

def mostrar_tabuleiro(tab, jogo):
    linhas = []
    grid_size = len(tab)
    linhas.append("🔹" + "".join([f"{i+1} " for i in range(grid_size)]) + "🔹")
    for r in range(grid_size):
        linha = LINHAS_EMOJI[r % len(LINHAS_EMOJI)] + " "
        for c in range(grid_size):
            letra = tab[r][c]
            achada = False
            for p in jogo["achadas"]:
                if (r, c) in p["coords"]:
                    achada = True
                    break
            if not achada and letra != ESPACO_VAZIO:
                letra = LETRA_OCULTA
            linha += letra + " "
        linha += LINHAS_EMOJI[r % len(LINHAS_EMOJI)]
        linhas.append(linha)
    linhas.append("🔹" + "".join([f"{i+1} " for i in range(grid_size)]) + "🔹")
    return "\n".join(linhas)

# ---------- COMANDO /apocalipse ----------
async def apocalipse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    palavras_disponiveis = carregar_palavras()
    if not palavras_disponiveis:
        await update.message.reply_text("❌ O arquivo palavras.txt está vazio!")
        return

    palavras = random.sample(palavras_disponiveis, min(MAX_WORDS, len(palavras_disponiveis)))
    tabuleiro, palavras_info = criar_tabuleiro(palavras)

    jogo_atual = {"palavras_info": palavras_info, "achadas": [], "tabuleiro": tabuleiro}
    jogos[update.effective_chat.id] = jogo_atual

    await update.message.reply_text(
        f"☣️ *APOCALIPSE MODE - CAÇA PALAVRAS*\n\n"
        f"🧩 Existem **{len(palavras_info)} palavras escondidas**.\n"
        "📝 Digite no chat o nome da palavra que encontrar.\n"
        "💡 Use /dica para receber uma dica automática.\n"
        "🏆 Use /ranking para ver o ranking de moedas.\n\n"
        f"{mostrar_tabuleiro(tabuleiro, jogo_atual)}",
        parse_mode="Markdown"
    )

# ---------- RECEBER PALAVRA NO CHAT (CORRIGIDO) ----------
async def receber_palavra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    usuarios_nome[user_id] = user_name

    # ❌ Ignora mensagens se não houver jogo ativo
    if chat_id not in jogos:
        return

    # ❌ Ignora mensagens que não parecem palavras
    texto = update.message.text.strip()
    if not texto.isalpha():  # só aceita texto com letras
        return

    tentativa = texto.upper()
    jogo = jogos[chat_id]
    palavras_achadas = [p["palavra"] for p in jogo["achadas"]]

    # ✅ Verifica se a tentativa corresponde a alguma palavra do jogo
    for p in jogo["palavras_info"]:
        if p["palavra"] in palavras_achadas:
            continue
        if tentativa == p["palavra"]:
            jogo["achadas"].append(p)
            usuarios_moedas[user_id] = usuarios_moedas.get(user_id, 0) + MOEDAS_POR_PALAVRA

            explosao = "💥✨🔥"
            await update.message.reply_text(
                f"{explosao}\n✅ {user_name} acertou: `{p['palavra']}`\n"
                f"💰 Ganhou {MOEDAS_POR_PALAVRA} moedas! Total: {usuarios_moedas[user_id]}\n"
                f"Palavras encontradas: {len(jogo['achadas'])}/{len(jogo['palavras_info'])}\n\n"
                f"{mostrar_tabuleiro(jogo['tabuleiro'], jogo)}",
                parse_mode="Markdown"
            )

            # ✅ Se todas as palavras forem encontradas
            if len(jogo["achadas"]) == len(jogo["palavras_info"]):
                usuarios_moedas[user_id] += PREMIO_FINAL
                await update.message.reply_text(
                    f"🏆 *VITÓRIA!*\nTodas as palavras foram encontradas!\n"
                    f"💰 Prêmio final: {PREMIO_FINAL} moedas\n"
                    f"Total de moedas: {usuarios_moedas[user_id]}"
                )
                del jogos[chat_id]
            return

    # ❌ Só responde “incorreta” se for uma tentativa plausível
    if len(tentativa) > 1:
        await update.message.reply_text(
            f"❌ Palavra incorreta: `{tentativa}`\nTente novamente!",
            parse_mode="Markdown"
        )

# ---------- DICA AUTOMÁTICA ----------
async def dar_dica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in jogos:
        await update.message.reply_text("⚠️ Nenhum jogo ativo. Use /apocalipse para começar.")
        return

    jogo = jogos[chat_id]
    palavras_achadas = [p["palavra"] for p in jogo["achadas"]]
    nao_encontradas = [p for p in jogo["palavras_info"] if p["palavra"] not in palavras_achadas]

    if not nao_encontradas:
        await update.message.reply_text("🏆 Todas as palavras já foram encontradas!")
        return

    palavra = random.choice(nao_encontradas)["palavra"]
    dica_texto = f"💡 DICA AUTOMÁTICA: A palavra começa com *{palavra[0]}* e tem *{len(palavra)}* letras"
    await update.message.reply_text(dica_texto, parse_mode="Markdown")

# ---------- RANKING ----------
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not usuarios_moedas:
        await update.message.reply_text("⚠️ Nenhuma moeda registrada ainda.")
        return
    top = sorted(usuarios_moedas.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏅 *Ranking de moedas*\n\n"
    for i, (uid, moedas) in enumerate(top, start=1):
        nome = usuarios_nome.get(uid, f"Usuário {uid}")
        msg += f"{i}. {nome} → {moedas} moedas\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("apocalipse", apocalipse))
    app.add_handler(CommandHandler("dica", dar_dica))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_palavra))
    print("🔥 Apocalypse Bot ONLINE")
    app.run_polling()

if __name__ == "__main__":
    main()
