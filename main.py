import hikari
import lightbulb
import miru
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pickle
import random
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

# Bot Token and SMTP Email Info (Gmail)
TOKEN = os.getenv("TOKEN")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS port
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# Initialize bot with intents
intents = hikari.Intents.ALL
bot = lightbulb.Bot(prefix="!", intents=intents, token=TOKEN)

# Only the bot owner can use the add_access command
YOUR_USER_ID = 850124068677746700

# Role ID for 🟡Access role
ACCESS_ROLE_ID = 1313275351861952554

# Notification channel ID
NOTIFICATION_CHANNEL_ID = 1310737995019714591

# Server-specific IDs
GUILD_ID = 1287178739893010484
VERIFICATION_CHANNEL_ID = 1315008309018890382
IMAGE_LINK_CHANNEL_ID = 1316877767060754432

# Data storage file paths
USER_EMAILS_FILE = "user_emails.pkl"
USER_RECEIPT_DATA_FILE = "user_receipt_data.pkl"

# Load persistent data or initialize new dictionaries
def load_data():
    if os.path.exists(USER_EMAILS_FILE):
        with open(USER_EMAILS_FILE, "rb") as file:
            user_emails = pickle.load(file)
    else:
        user_emails = {}
    
    if os.path.exists(USER_RECEIPT_DATA_FILE):
        with open(USER_RECEIPT_DATA_FILE, "rb") as file:
            user_receipt_data = pickle.load(file)
    else:
        user_receipt_data = {}
    
    return user_emails, user_receipt_data

user_emails, user_receipt_data = load_data()

# Save data function
def save_data():
    with open(USER_EMAILS_FILE, "wb") as file:
        pickle.dump(user_emails, file)
    
    with open(USER_RECEIPT_DATA_FILE, "wb") as file:
        pickle.dump(user_receipt_data, file)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.sync_commands()

@bot.command()
async def subscription(ctx, user_id: int):
    embed = hikari.Embed(
        title="Subscription Expired",
        description=f"<@{user_id}>, your subscription has ended, and access to the receipt generator has been removed.",
        color=0x9B59B6
    )
    await ctx.respond(embed=embed)

@bot.command()
@lightbulb.option("member", hikari.Member, "The user to add access to")
@lightbulb.option("days", int, "The number of days to grant access", required=False)
@lightbulb.option("forever", bool, "Grant access forever", required=False)
async def add_access(ctx: lightbulb.Context, member: hikari.Member, days: int = None, forever: bool = False):
    if ctx.author.id != YOUR_USER_ID:
        await ctx.respond("You are not authorized to use this command.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    role = ctx.get_guild().get_role(ACCESS_ROLE_ID)
    if not role:
        await ctx.respond("The 🟡Access role does not exist.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    notification_message = ""
    if forever:
        await member.add_role(role)
        notification_message = f"Access granted to {member.mention} indefinitely."
    elif days:
        await member.add_role(role)
        expiration_date = datetime.now() + timedelta(days=days)
        notification_message = f"Access granted to {member.mention} for {days} days. Access will expire on {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}."
    else:
        await ctx.respond("You must specify either 'forever' or a 'days' value.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    notification_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if notification_channel:
        await notification_channel.send(f"""
        Access granted to {member.mention}.
        Thank you for choosing Brand Receipts, {member.mention}. You can use the receipt generator by typing /generator.
        Please vouch for us in <#{VERIFICATION_CHANNEL_ID}> ⭐•reviews.
        To renew your subscription, visit <#{NOTIFICATION_CHANNEL_ID}> 🛒purchase.
        """)
    await ctx.respond(f"Access granted. {notification_message}", flags=hikari.MessageFlag.EPHEMERAL)

@bot.command()
@lightbulb.option("email", str, "Set up your email to use the receipt generator.")
async def setup_email(ctx: lightbulb.Context, email: str):
    user_id = ctx.author.id

    if user_id in user_emails:
        await ctx.respond("You have already set up an email. If you need to change it, please contact an admin.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    user_emails[user_id] = email
    save_data()  # Save changes to disk

    channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
    if channel:
        await channel.send(f"Email submitted for verification: {email} (User: {ctx.author})")

    await ctx.respond("Start Generating Receipt Now.", flags=hikari.MessageFlag.EPHEMERAL)

@bot.command()
async def generate_receipt(ctx: lightbulb.Context):
    user_id = ctx.author.id

    if user_id not in user_emails:
        await ctx.respond("You need to set up your email first using /setup_email.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    user_receipt_data[user_id] = {}
    save_data()  # Save initialized data

    class BrandSelect(miru.Select):
        def __init__(self):
            options = [
                hikari.SelectOption(label="⭐Apple"),
            ]
            super().__init__(placeholder="Select the brand name...", options=options)

        async def callback(self, select_interaction: hikari.Interaction):
            user_receipt_data[user_id]['brand_name'] = self.values[0]
            save_data()  # Save the selected brand name
            await select_interaction.response.send_message(f"Brand name set to: {self.values[0]}", flags=hikari.MessageFlag.EPHEMERAL)
            self.stop()

    view = miru.View()
    view.add_item(BrandSelect())

    await ctx.respond("Please select the brand name:", view=view)
    await view.wait()

    # Use hikari form for user input
    class ReceiptForm(hikari.abc.Modal):
        def __init__(self):
            super().__init__(title="Receipt Generator")
            self.add_text_input("What is your name and surname?", max_length=100, required=True)
            self.add_text_input("What is your phone number?", max_length=15, required=True)
            self.add_text_input("What is the billing address?", max_length=200, required=True)
            self.add_text_input("What is the shipping address?", max_length=200, required=True)
            self.add_text_input("What is the product name?", max_length=100, required=True)
            self.add_text_input("What is the price of the product?", max_length=10, required=True)
            self.add_text_input("What currency would you like your receipt to be in? (e.g. £, $, €)", max_length=5, required=True)
            self.add_text_input("What is the shipping cost?", max_length=10, required=True)
            self.add_text_input("What is the total for the order?", max_length=10, required=True)
            self.add_text_input("What is the total after tax?", max_length=10, required=True)
            self.add_text_input("What is the order date? (e.g., YYYY-MM-DD)", max_length=10, required=True)
            self.add_text_input("What is the expected delivery date? (e.g., YYYY-MM-DD)", max_length=10, required=True)
            self.add_text_input("What is the payment method?", max_length=50, required=True)
            self.add_text_input("Please provide the product image URL.", max_length=500, required=True)

        async def callback(self, context: hikari.abc.Context):
            for field, value in context.values.items():
                user_receipt_data[user_id][field] = value
            save_data()  # Save after form submission

            # Send Email Logic
            result = send_email_via_smtp_html(user_receipt_data[user_id], user_emails[user_id], user_receipt_data[user_id].get('brand_name', 'Unknown Brand'))

            if result:
                await context.respond("Receipt generated successfully!", flags=hikari.MessageFlag.EPHEMERAL)
            else:
                await context.respond("There was an error generating the receipt email.", flags=hikari.MessageFlag.EPHEMERAL)

    await ReceiptForm().send(ctx.author)

def send_email_via_smtp_html(receipt_data, to_email, brand_name):
    template_dir = "C:/Users/xray/Downloads/receipt_email/"
    env = Environment(loader=FileSystemLoader(template_dir))

    # Load the appropriate template based on brand_name
    template_file = f"{brand_name.lower()}.html"
    default_template_file = "default.html"

    try:
        # Try to load the specific brand template; fallback to the default if necessary
        if os.path.exists(os.path.join(template_dir, template_file)):
            template = env.get_template(template_file)
        else:
            template = env.get_template(default_template_file)

        # Assemble data for the template
        order_number = random.randint(100000, 999999)
        data = {
            "name_surname": receipt_data.get('name_surname', 'Unknown'),
            "email": receipt_data.get('email', 'N/A'),
            "phone_number": receipt_data.get('phone_number', 'N/A'),
            "BILLING1": receipt_data.get('billing_address', '').replace(',', '\n'),  # Split billing address lines if needed
            "ADDRESS1": receipt_data.get('shipping_address', '').replace(',', '\n'),  # Split shipping address lines if needed
            "PRODUCT_NAME": receipt_data.get('product_name', 'N/A'),
            "PRODUCT_PRICE": receipt_data.get('price', '0'),
            "currency": receipt_data.get('currency', 'USD'),
            "shipping_cost": receipt_data.get('shipping_cost', '0'),
            "ORDER_TOTAL": receipt_data.get('total_for_order', '0'),
            "ORDERNUMBER": order_number,  # This will be the generated number
            "DATE": receipt_data.get('order_date', 'N/A'),
            "delivery_date": receipt_data.get('delivery_date', 'N/A'),
            "payment_method": receipt_data.get('payment_method', 'N/A'),
            "PRODUCT_IMAGE": receipt_data.get('image_url', 'N/A'),
        }

        # Render the template with the data
        html_content = template.render(data)

        # Logging the rendered HTML content for debugging
        print(f"Rendered HTML Content for {to_email}: {html_content}")

        # Determine the email subject
        if brand_name.lower() == "apple":
            subject = f"🎉 Your order has been shipped from {brand_name}"
        elif brand_name.lower() == "stockx_new_delivered":
            subject = f"🎉 Order Delivered: {receipt_data.get('product_name', 'N/A')}"
        else:
            subject = "🎉 We're processing your order "

        # Set up the email message
        message = MIMEMultipart()
        message["From"] = FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        # Send the email via SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, message.as_string())

        print("Email sent successfully.")
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False

bot.run()
