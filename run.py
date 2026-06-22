"""نقطة التشغيل — يحمّل .env تلقائياً"""
from dotenv import load_dotenv
load_dotenv()

from bot import main
main()
