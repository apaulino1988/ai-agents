# A2P 10DLC Registration Runbook — Paulino AI Agents LLC

**Purpose:** unblock US SMS delivery (Twilio error 30034) by registering the
LLC as a Standard brand with a Low-Volume Mixed campaign. Written 2026-11-23
so filing is a ~30-minute task the day the EIN arrives.

**Status:** WAITING on prerequisites (LLC + EIN). Fees verified 2026-11-23
against [Twilio's fee page](https://support.twilio.com/hc/en-us/articles/1260803965530)
(TCR raised fees 2025-08-01).

## Prerequisites (from the LLC formation plan)

- [ ] LLC approved — legal name EXACTLY `Paulino AI Agents LLC`, SDAT ID
- [ ] EIN (9 digits)
- [ ] Business address (the registered principal office address)
- [ ] Business website URL with a privacy policy and SMS opt-in language
      (see "Landing page" below — TCR vetting checks this)
- [ ] Twilio account upgraded out of trial (card on file) — required for
      Standard brand registration

## Fees (budget ~$65 one-time + ~$3.50/mo)

| Item | Cost | When |
|------|------|------|
| Brand registration | $4.50 one-time | At brand submit |
| Standard (secondary) vetting | $41.50 one-time | At brand submit |
| Campaign vetting | $15 one-time | At campaign submit |
| Low-Volume Mixed campaign | $1.50/mo | Recurring |
| Carrier passthrough per SMS segment | fractions of a cent | Usage |

## Landing page (do first — vetting looks at it)

A one-page site at the LLC domain with: what the service is, contact email,
**privacy policy** (customer data not sold/shared with third parties for
marketing), and **SMS disclosure**: "By texting our number or providing your
phone number when booking, you consent to receive appointment-related
messages. Reply STOP to opt out, HELP for help. Message/data rates may
apply." Claude can generate this page; host free on GitHub Pages under the
custom domain until the real site exists.

## Filing steps (Twilio Console)

1. **Trust Hub — Customer Profile (Secondary):** Console → Trust Hub →
   Customer Profiles → create:
   - Legal business name: `Paulino AI Agents LLC` (must match SDAT record)
   - Business type: Limited Liability Company · Business identity: EIN, the 9 digits
   - Industry: `Technology` · Website: the LLC domain
   - Authorized representative: Andres Paulino, title `Owner/Member`, business email (not gmail if Workspace is live; gmail accepted but weaker vetting signal)
2. **A2P Brand:** Messaging → Regulatory Compliance → Onboarding → register
   **Standard Brand** attached to that profile. Pay $4.50 + $41.50. Vetting
   returns a score; LOW score still registers but limits throughput —
   accept and proceed (appeal is $11 if clearly wrong).
3. **Messaging Service:** Messaging → Services → create `paulino-ai-agents`
   → add the number `+1 908 663 8552` to its sender pool. Set inbound
   webhook on the service to the production `/webhooks/sms` URL (or keep
   number-level webhook until aws-deploy cutover).
4. **Campaign:** under the brand, create campaign:
   - Use case: **Low-Volume Mixed**
   - Description: `Appointment scheduling assistant for small businesses.
     Customers message us or book online; we send booking confirmations,
     appointment reminders, and replies to customer-initiated questions, in
     English and Spanish.`
   - Sample message 1: `Hi Maria! Reminder: your Dental Cleaning & Exam is
     Mon Nov 30 at 10:00 AM at 123 Main St. Reply CONFIRM to confirm, or
     call (301) 555-0100 to reschedule. Reply STOP to opt out.`
   - Sample message 2: `¡Hola María! Recordatorio: su cita de limpieza
     dental es el lunes 30 de nov a las 10:00 AM. Responda CONFIRM para
     confirmar. Responda STOP para cancelar mensajes.`
   - Opt-in description: `End users opt in by initiating a conversation
     with the business via SMS/WhatsApp, or by providing their phone number
     during booking (web chat or in person) and agreeing to receive
     appointment-related messages. Opt-in disclosure is published at
     <landing page URL>.`
   - Opt-in type: both `Via text` and `Verbal/Web form`
   - Embedded link/phone: No embedded links in messages; phone numbers yes
   - Opt-out: STOP/HELP handled by Twilio **Advanced Opt-Out** on the
     Messaging Service (enable it — default keywords EN + add Spanish:
     ALTO/AYUDA as custom keywords)
   - Pay $15 vetting; recurring $1.50/mo starts on approval
5. **Wait:** campaign vetting runs days to ~2 weeks (external TCR/carrier
   clock). Status shows in Console → Compliance.

## After approval

- [ ] Send a live SMS to Andres's handset via the API — the M3 deferred
      carrier-edge verification (error 30034 should be gone)
- [ ] Re-run the SMS leg of `docs/smoke-test.md`
- [ ] Record result in `.add/handoff.md` + PRD M4 hill chart
- [ ] Check the campaign's daily throughput assigned by carriers (T-Mobile
      daily cap depends on vetting score) — fine at current volume

## Notes

- WhatsApp is unaffected by 10DLC (separate Meta path, already ONLINE).
- When Meta business verification docs are submitted, use the same LLC
  legal name so Twilio, Meta, and Stripe all match.
- If vetting rejects: commonest causes are website missing opt-in language
  or name mismatch — fix and resubmit, appeal only for scoring disputes.
