# Payment Request — Onboarding

سند آشنایی با ماژول `payment_request` برای توسعه‌دهنده جدید.

## Purpose

درخواست پرداخت (Payment Request) — یک فرم مالی که کاربران ثبت می‌کنند، مدیر واحد تایید/رد می‌کند، حسابدار مراحل را بررسی و پرداخت را قطعی می‌کند. داده‌های پایه (واحد سازمانی، طرف حساب، مرکز هزینه) از انبار داده MSSQL شرکت (Shaka_DW) می‌آیند و مقادیر طبقه‌بندی از ماژول `generic_lookup`.

## Module map

```
addons/payment_request/
├── models/
│   ├── models.py           # همه مدل‌ها: main + 4 subform + workflow + شماره‌گذاری
│   ├── dim_company.py      # odoo.raes.dim.company  (SQL view over raees_dim_company_view)
│   ├── dim_party.py        # odoo.raes.dim.party    (SQL view over raes_dim_party_view)
│   └── dim_cost_center.py  # odoo.raes.dim.cost_center (SQL view over raes_dim_cost_center_view, FDW → MSSQL)
├── security/
│   ├── security.xml        # گروه‌ها (حسابدار، مدیر واحد) + record rules
│   └── ir.model.access.csv # ACL ها
├── data/
│   └── lookup_data.xml     # دنباله شماره + انواع lookup (بابت پرداخت، نوع پرداخت)
└── views/views.xml         # list/form/action/menu
```

## Models

| Model                             | نقش                                                                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `payment_request.payment_request` | فرم اصلی: شماره، تاریخ، واحد سازمانی، طرف حساب، بابت، رسمی/غیر رسمی، توضیحات، وضعیت گردش کار                                                 |
| `payment_request.detail`          | جزئیات درخواست پرداخت: شرح، نوع پرداخت (lookup)، مرکز هزینه (DW)، مبلغ، ارزش افزوده، مبلغ خالص (computed = مبلغ + ارزش افزوده)، تاریخ توافقی |
| `payment_request.stage`           | مرحله پرداخت: ۶ مرحله ثابت با state سه‌وضعیتی (بررسی نشده/تایید شده/رد شده) — فقط حسابدار                                                    |
| `payment_request.extra`           | اطلاعات تکمیلی (key/value آزمایشی)                                                                                                           |
| `payment_request.paid`            | اطلاعات پرداخت شده (تاریخ/مبلغ/شرح آزمایشی)                                                                                                  |
| `lookup.type` / `lookup.value`    | از `generic_lookup` — بابت پرداخت (`payment_reason`)، نوع پرداخت (`payment_type`)                                                            |

خواندنی‌های DW (`_auto = False`, read-only): dropdown «واحد سازمانی»، «طرف حساب»، «مرکز هزینه» مستقیماً از view های دیتابیس تغذیه می‌شوند.

## Workflow

```
draft ──submit──▶ unit_review ──accept──▶ accounting ──accept──▶ accounting_approved ──mark paid──▶ paid
                      │
                      └──reject──▶ rejected
```

- **کاربر عادی**: ثبت و ارسال (`action_submit`)، فقط رکوردهای خودش را می‌بیند.
- **مدیر واحد** (`payment_request.group_unit_manager`): درخواست‌های ارجاع‌شده به خودش را می‌بیند (`unit_manager_id`)، تایید/رد می‌کند. **مرحله پرداخت برای او مخفی است.**
- **حسابدار** (`payment_request.group_accountant`): همه را می‌بیند، مراحل را وضعیت‌دهی می‌کند، بعد از مدیر تایید نهایی و «پرداخت شد».
- **Site admin** (`base.group_system`): همه چیز.
- هر گذار state یک پیام در chatter می‌گذارد و به فرد بعدی در زنجیره اطلاع‌رسانی می‌کند (`mail.thread` + `<chatter/>`).

State ها: `draft` پیش‌نویس، `unit_review` در انتظار مدیر واحد، `rejected` رد شده، `accounting` در انتظار حسابدار، `accounting_approved` تایید حسابدار، `paid` پرداخت شده.

## Numbering (شماره)

- خودکار، `readonly` در فرم، مقداردهی در `create()` از `_next_number()`.
- **شماره = MAX(شماره‌های عددی رکوردهای همین سال شمسی) + 1** → هر اول فروردین از 1 شروع می‌شود.
- تبدیل میلادی↔شمسی با توابع محلی `_gregorian_to_jalali` / `_jalali_to_gregorian` (بدون وابستگی).
- `UNIQUE(number)` — رکوردهای قدیمی غیرعددی نادیده گرفته می‌شوند (regex `^[0-9]+$`).
- سال شمسی از `date` رکورد گرفته می‌شود، نه تاریخ امروز.

## Record rules (visibility)

| گروه | دامنه |
|---|---|
| `base.group_user` | `create_uid = خودم` |
| `group_unit_manager` | `unit_manager_id = خودم` یا `create_uid = خودم` |
| `group_accountant` | همه |
| `base.group_system` | همه |

قوانین OR می‌شوند؛ عضویت در چند گروه بهترین دسترسی را می‌دهد.

## Stage steps (مراحل ثابت)

در `PaymentRequest.STAGE_STEPS` هاردکد شده‌اند، ترتیب:
1. فاکتور رسمی
2. ثبت در سامانه مودیان
3. صحیح بودن نام کالا در سامانه مودیان
4. ثبت رسید انبار
5. صحیح بودن مانده بدهی
6. ضمیمه شده قرارداد های امضا شده

در `create()` با `sudo()` ساخته می‌شوند (کاربر عادی perm create روی stage ندارد) و state اولیه `unattended` می‌گیرند. سطرها قابل حذف/افزودن/جابجایی نیستند.

## Setup for a new environment

1. ماژول‌ها را نصب/آپگرید کنید:
   ```bash
   python ./odoo-bin -c odoo.conf -d <db> -u payment_request --stop-after-init --no-http
   ```
   (اگر سرویس روی 8069 بالا است حتماً `--no-http` تا تداخل پورت پیش نیاید.)
2. کاربران را در گروه‌ها بگذارید: Settings → Users → بخش «درخواست پرداخت» → حسابدار / مدیر واحد.
3. مقادیر lookup را بسازید: منوی Lookup Data → Values:
   - نوع «بابت پرداخت» (code `payment_reason`)
   - نوع «نوع پرداخت» (code `payment_type`)
4. FDW و user mapping برای دسترسی `odoo` به `raes_dim_*_view` باید از قبل برقرار باشد (MSSQL linked server).

## Dev notes / gotchas

- **container نزنید** — این ریپو local است؛ odoo با `python ./odoo-bin` روی سیستم اجرا می‌شود (venv: `.venv`).
- تغییر Python فقط restart؛ تغییر XML/CSV حتماً `-u payment_request`.
- بعد از تغییر view اگر UI عجیب بود: assets را پاک کنید:
  ```sql
  DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';
  ```
  و hard refresh (Ctrl+Shift+R).
- Modifier های view (`invisible=`/`readonly=`) به فیلدهای compute (`is_accountant`, `is_unit_manager`, `is_site_admin`) ارجاع می‌دهند؛ این سه فیلد باید به صورت `invisible="1"` در form باقی بمانند وگرنه web client modifier را نمی‌شناسد.
- Odoo 19: chatter با تگ `<chatter/>` (نه div با کلاس `oe_chatter`)، SQL constraint با `models.Constraint`، گروه‌ها با `res.groups.privilege`.
- `number` عمداً `required=True` ندارد؛ readonly + required + خالی باعث بلاک شدن save در کلاینت می‌شود — مقدار در `create()` تضمین شده است.
- Pyright روی `selection=`, `next_by_code`, `message_post`, `has_group` خطای کاذب می‌دهد (stubs ندارند) — نادیده بگیرید.
- مقداردهی stage همیشه سمت سرور: `vals['stage_ids']` از کلاینت پاپ می‌شود.
