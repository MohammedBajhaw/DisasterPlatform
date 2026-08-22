#!/bin/bash

# Disaster Platform - Quick Sync Script 🚀

# الألوان لتنسيق المخرجات
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # بدون لون

# الانتقال لمسار المشروع
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}   🔄 مزامنة مشروع DisasterPlatform مع GitHub${NC}"
echo -e "${BLUE}==========================================${NC}"

# التحقق من وجود تغييرات
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}ℹ️ لا توجد أي تغييرات جديدة لرفعها! المشروع محدث بالكامل.${NC}"
    exit 0
fi

# عرض الملفات التي تغيرت
echo -e "\n${YELLOW}📂 التغييرات المكتشفة:${NC}"
git status -s

echo -e "\n${BLUE}------------------------------------------${NC}"
# طلب رسالة التعديل من المستخدم
read -r -p "📝 اكتب وصف التعديل (أو اضغط Enter لاستخدام الوصف التلقائي): " commit_msg

# إذا ترك المستخدم الرسالة فارغة، نضع وصفاً تلقائياً بالتاريخ والوقت
if [ -z "$commit_msg" ]; then
    commit_msg="Update: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${YELLOW}⚡ سيتم استخدام الوصف الافتراضي: \"$commit_msg\"${NC}"
fi

echo -e "\n${BLUE}⏳ جاري تجهيز ورفع التعديلات إلى GitHub...${NC}"

# إضافة جميع التعديلات
git add .

# حفظ التعديل
git commit -m "$commit_msg"

# رفع التعديل للفرع الرئيسي
if git push origin main; then
    echo -e "\n${GREEN}==========================================${NC}"
    echo -e "${GREEN}  ✅ تم رفع التعديلات بنجاح إلى GitHub! 🎉${NC}"
    echo -e "${GREEN}  🔗 https://github.com/MohammedBajhaw/DisasterPlatform${NC}"
    echo -e "${GREEN}==========================================${NC}"
else
    echo -e "\n${RED}❌ حدث خطأ أثناء محاولة الرفع. يرجى التحقق من اتصال الإنترنت أو إعدادات الصلاحيات.${NC}"
fi
