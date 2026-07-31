import json
import os
import random
import re
from collections import Counter

# CONFIGURATION
# Default paths (relative to where script is run, usually root)
DEFAULT_CHAT_PATH = os.path.join("backend", "_chat.txt")
OUTPUT_FILE = os.path.join("backend", "app", "personality.json")


def parse_whatsapp_chat(file_path):
    """
    Parses a standard WhatsApp export file (_chat.txt).
    Returns a list of messages: [{'sender': str, 'message': str, 'timestamp': datetime}]
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found at {file_path}")
        return []

    print(f"📂 Reading chat file: {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    messages = []

    # Regex Patterns for different device formats
    # iOS: [20/01/24, 10:30:00 PM] Sender: Message
    ios_pattern = re.compile(
        r"\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}:\d{2}.*?)\]\s*(.*?):\s*(.*)"
    )

    # Android: 20/01/24, 10:30 am - Sender: Message
    android_pattern = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}.*?)\s*-\s*(.*?):\s*(.*)"
    )

    success_count = 0

    for line in lines:
        line = line.strip()
        # skip empty
        if not line:
            continue

        # Try iOS
        match = ios_pattern.match(line)
        if not match:
            # Try Android
            match = android_pattern.match(line)

        if match:
            sender = match.group(3).strip()
            message = match.group(4).strip()

            # Filter out system messages
            if (
                "omitted" in message
                or "security code changed" in message
                or "Messages to this chat and calls" in message
            ):
                continue

            # Filter out "You deleted this message"
            if "deleted this message" in message:
                continue

            messages.append({"sender": sender, "message": message})
            success_count += 1

    print(f"✅ Successfully parsed {success_count} messages.")
    return messages


def extract_personality_data(messages, her_name, my_name):
    """
    Analyzes messages to find common voice patterns and interaction examples.
    STRICT MODE: Only accepts Me -> Her patterns where names match exactly.
    """
    her_messages = [m["message"] for m in messages if m["sender"] == her_name]

    if not her_messages:
        print(f"❌ No messages found for sender '{her_name}'.")
        return None

    print(f"🧠 Analyzing {len(her_messages)} messages from '{her_name}'...")

    # 1. Vocabulary Extraction (Top Hinglish words)
    all_words = []
    for msg in her_messages:
        # Remove punctuation but keep Hindi/Roman chars
        clean_msg = re.sub(r"[^\w\s]", "", msg.lower())
        all_words.extend(clean_msg.split())

    vocab_counter = Counter(all_words)
    # Get top 50 strictly alphabetical words (no numbers)
    top_vocab = [
        w for w, c in vocab_counter.most_common(200) if w.isalpha() and len(w) > 2
    ]
    final_vocab = top_vocab[:40]

    # 2. Dialogue Extraction (Pattern: Me -> Her -> [Her])
    # We want "threads" not just pairs. Sometimes she replies in 2 messages.
    dialogue_examples = []

    i = 0
    while i < len(messages) - 2:
        curr = messages[i]
        next_1 = messages[i + 1]
        next_2 = messages[i + 2]

        # Pattern 1: Simple Pair (Me -> Her)
        if curr["sender"] == my_name and next_1["sender"] == her_name:
            user_text = curr["message"]
            her_text = next_1["message"]

            # Check if she sent a double text (Me -> Her -> Her)
            if next_2["sender"] == her_name:
                # Combine her messages for fuller context
                her_text += f" {next_2['message']}"
                i += 1  # Skip extra step

            # Filters
            if len(her_text.split()) < 3:
                i += 1
                continue  # Skip very short like "Haan ok"
            if len(her_text.split()) > 40:
                i += 1
                continue  # Skip huge essays
            if "<Media omitted>" in user_text or "<Media omitted>" in her_text:
                i += 1
                continue

            dialogue_examples.append({"user": user_text, "response": her_text})
        i += 1

    print(f"🔍 Found {len(dialogue_examples)} valid dialogue threads.")

    # Scoring: Prioritize length and Hinglish vocabulary
    scored_examples = []
    for ex in dialogue_examples:
        score = 0
        txt = ex["response"].lower()
        # Bonus for length (more context)
        score += len(txt.split()) * 0.5
        # Bonus for vocab
        for v in final_vocab[:20]:
            if v in txt:
                score += 2
        scored_examples.append((score, ex))

    # Sort and Select
    scored_examples.sort(key=lambda x: x[0], reverse=True)

    # INCREASED LIMIT: Top 60 examples (30 best + 30 random from top 200)
    top_picks = [x[1] for x in scored_examples[:30]]

    remaining_pool = scored_examples[30:230]
    if remaining_pool:
        random_picks = [
            x[1] for x in random.sample(remaining_pool, min(30, len(remaining_pool)))
        ]
    else:
        random_picks = []

    final_examples = top_picks + random_picks
    random.shuffle(final_examples)

    return {"vocabulary": final_vocab, "examples": final_examples}


def update_personality_json(data):
    if not os.path.exists(OUTPUT_FILE):
        print(f"❌ Error: {OUTPUT_FILE} not found. Run this from project root.")
        return

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            personality = json.load(f)
    except Exception as e:
        print(f"❌ Error reading personality.json: {e}")
        return

    # Update Style
    personality["speaking_style"] = personality.get("speaking_style", {})
    personality["speaking_style"]["style_description"] = (
        "Natural Hinglish (Hindi + English Mix). Casual, uses Roman Hindi frequently."
    )
    personality["speaking_style"]["common_vocabulary"] = data["vocabulary"]

    # Update Examples
    personality["example_dialogues"] = data["examples"]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(personality, f, indent=2, ensure_ascii=False)

    print("✨ Updated personality.json with:")
    print(f"   - {len(data['vocabulary'])} common words")
    print(f"   - {len(data['examples'])} extended dialogue threads")
    print("✅ Done! Validated and Saved.")


def main():
    print("--- 🧠 AI Soul Ingestor (WhatsApp Edition v2) ---")

    chat_path = input(
        f"Enter path to _chat.txt (default: {DEFAULT_CHAT_PATH}): "
    ).strip()
    if not chat_path:
        chat_path = DEFAULT_CHAT_PATH

    if not os.path.exists(chat_path):
        print(f"❌ File not found: {chat_path}")
        return

    messages = parse_whatsapp_chat(chat_path)
    if not messages:
        print("❌ No messages parsed. Check file format.")
        return

    # Auto-detect names
    counts = Counter([m["sender"] for m in messages])
    print("\nTop Senders found:")
    top_senders = counts.most_common(10)
    for i, (name, count) in enumerate(top_senders):
        print(f"  {i + 1}. {name} ({count} msgs)")

    print("\n👉 Who is the person you want to clone (HER)?")
    choice_her = input("Choice (Number): ").strip()
    if not choice_her.isdigit() or int(choice_her) > len(top_senders):
        print("❌ Invalid choice.")
        return
    her_name = top_senders[int(choice_her) - 1][0]

    print("\n👉 Who are YOU (ME)? (Crucial for correct Q&A pairs)")
    choice_me = input("Choice (Number): ").strip()
    if not choice_me.isdigit() or int(choice_me) > len(top_senders):
        print("❌ Invalid choice.")
        return
    my_name = top_senders[int(choice_me) - 1][0]

    if her_name == my_name:
        print("❌ You cannot be the same person! Choose distinct senders.")
        return

    print(f"\n🔮 Extracting soul of '{her_name}' based on chats with '{my_name}'...")
    data = extract_personality_data(messages, her_name, my_name)

    if data:
        update_personality_json(data)


if __name__ == "__main__":
    main()
