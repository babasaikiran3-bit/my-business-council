# Stripe Payment Integration Setup Guide

This guide will help you set up Stripe payment processing for the LLM Council application (Features 4 & 5: Paywall & 7-Day Retention).

## Overview

The application now includes:
- **Freemium Model**: 2 free conversations, then paywall
- **3 Subscription Tiers**: Single Report (€1.99), Monthly (€7.99/month), Yearly (€70/year)
- **7-Day Grace Period**: Free reports expire after 7 days
- **Auto-Restore**: All expired reports restored on subscription

## 1. Create Stripe Account

### Test Mode Setup

1. Go to https://dashboard.stripe.com/register
2. Create your Stripe account
3. **Switch to Test Mode** (toggle in the top-right corner)
4. You'll use test mode API keys for development

## 2. Get Your API Keys

### From Stripe Dashboard (Test Mode)

1. Navigate to **Developers** → **API keys**
2. You'll see two keys:
   - **Publishable key** (starts with `pk_test_...`)
   - **Secret key** (starts with `sk_test_...`) - Click "Reveal test key"

## 3. Set Up Webhook Endpoint

### Configure Stripe Webhooks

1. Go to **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. Set the endpoint URL:
   ```
   http://localhost:8001/api/webhooks/stripe
   ```
   (For production, use your actual domain)

4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`

5. Click **Add endpoint**
6. Copy the **Signing secret** (starts with `whsec_...`)

## 4. Configure Environment Variables

### Backend (.env file)

Add these to `backend/.env`:

```bash
# Stripe API Keys (Test Mode)
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Existing keys (keep these)
OPENROUTER_API_KEY=your_openrouter_key
CLERK_SECRET_KEY=your_clerk_secret_key
ADMIN_API_KEY=your_admin_key
```

### Frontend (.env file)

The frontend doesn't need Stripe keys directly (we use Stripe Checkout hosted pages).

## 5. Test Payment Flow

### Using Stripe Test Cards

Stripe provides test card numbers for development:

#### Successful Payment
```
Card number: 4242 4242 4242 4242
Expiry: Any future date (e.g., 12/25)
CVC: Any 3 digits (e.g., 123)
ZIP: Any 5 digits (e.g., 12345)
```

#### Declined Payment
```
Card number: 4000 0000 0000 0002
Expiry: Any future date
CVC: Any 3 digits
ZIP: Any 5 digits
```

More test cards: https://stripe.com/docs/testing

### Testing Webhooks Locally

#### Option 1: Stripe CLI (Recommended)

1. Install Stripe CLI:
   ```bash
   # Windows
   scoop install stripe

   # Mac
   brew install stripe/stripe-cli/stripe

   # Linux
   # Download from https://github.com/stripe/stripe-cli/releases
   ```

2. Login to Stripe:
   ```bash
   stripe login
   ```

3. Forward webhooks to your local server:
   ```bash
   stripe listen --forward-to localhost:8001/api/webhooks/stripe
   ```

4. This will give you a webhook signing secret (starts with `whsec_...`)
5. Update your `.env` file with this secret

#### Option 2: Manual Testing

1. Make a test purchase through the UI
2. Check Stripe Dashboard → **Events** to see webhook delivery
3. Manually trigger webhooks from the dashboard if needed

## 6. Verify Integration

### Test Checklist

- [ ] **Free Tier**: Create 2 conversations successfully
- [ ] **Paywall Trigger**: 3rd conversation attempt shows paywall
- [ ] **Stripe Checkout**: Clicking subscription opens Stripe payment page
- [ ] **Test Payment**: Complete payment with test card
- [ ] **Webhook Receipt**: Backend receives webhook event
- [ ] **Subscription Update**: User's subscription tier updates in database
- [ ] **Report Restoration**: Previously expired reports become visible
- [ ] **Expiration Display**: Free conversations show "X days left" badge

### Check Database Files

After successful payment, verify:

```bash
# Check subscription file was created
ls data/subscriptions/

# View subscription details
cat data/subscriptions/<user_id>.json

# Check conversations were restored
ls data/conversations/
```

## 7. Monitor and Debug

### Useful Stripe Dashboard Pages

- **Payments**: See all test payments
- **Customers**: View created customers
- **Subscriptions**: Monitor active subscriptions
- **Events**: See all webhook events and their delivery status
- **Logs**: API request logs

### Common Issues

#### Webhooks Not Received

**Problem**: Payment succeeds but subscription doesn't update

**Solutions**:
1. Check webhook endpoint URL is correct
2. Verify `STRIPE_WEBHOOK_SECRET` matches the webhook endpoint
3. Use Stripe CLI to forward webhooks locally
4. Check backend logs for webhook errors

#### Payment Succeeds but User Not Upgraded

**Problem**: Payment completed but user still sees paywall

**Solutions**:
1. Check backend logs for webhook processing errors
2. Verify `user_id` is correctly passed in checkout metadata
3. Check `data/subscriptions/<user_id>.json` was created/updated
4. Reload the page to fetch updated subscription

#### Stripe Checkout Not Loading

**Problem**: Clicking subscription shows error

**Solutions**:
1. Verify `STRIPE_SECRET_KEY` is set correctly in backend
2. Check backend logs for Stripe API errors
3. Ensure backend is running on port 8001
4. Check browser console for network errors

## 8. Production Deployment

### Before Going Live

1. **Switch to Live Mode** in Stripe Dashboard
2. Get your **Live API keys** (starts with `pk_live_...` and `sk_live_...`)
3. Update production environment variables
4. Set webhook endpoint to production URL
5. Update `frontend_base` URLs in `backend/main.py`:
   ```python
   frontend_base = "https://yourdomain.com"  # Update this
   ```

### Update Pricing (Optional)

Edit prices in `backend/stripe_integration.py`:

```python
SUBSCRIPTION_PLANS = {
    "single_report": {
        "price": 199,  # €1.99 in cents - adjust before production
        ...
    },
    "monthly": {
        "price": 799,  # €7.99 in cents - adjust before production
        ...
    },
    "yearly": {
        "price": 7000,  # €70 in cents - adjust before production
        ...
    },
}
```

### Production Webhook Setup

1. In Stripe Dashboard (Live Mode), go to **Webhooks**
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select same events as test mode
4. Copy the Live webhook secret
5. Update production environment with live keys

## 9. Testing Recommendations

### Manual Test Flow

1. **Sign Up**: Create new account → Complete onboarding
2. **Free Usage**: Create 2 conversations
3. **Paywall Hit**: Try to create 3rd conversation → See paywall
4. **Purchase Flow**:
   - Click "Subscribe Monthly" (or any tier)
   - Complete payment with test card
   - Redirect to success page
5. **Verify Upgrade**:
   - Check sidebar shows "⭐ Monthly Plan"
   - Verify can create unlimited conversations
   - Check expired reports are restored (if any)

### Automated Testing (Future)

Consider adding tests for:
- Webhook signature verification
- Subscription upgrade/downgrade logic
- Report expiration calculations
- Access control enforcement

## 10. Support and Resources

- **Stripe Documentation**: https://stripe.com/docs
- **Stripe Testing**: https://stripe.com/docs/testing
- **Webhook Documentation**: https://stripe.com/docs/webhooks
- **Stripe CLI**: https://stripe.com/docs/stripe-cli
- **Support**: https://support.stripe.com

## Architecture Summary

```
User Flow:
1. User hits paywall (3rd conversation)
2. Clicks subscription tier → Redirected to Stripe Checkout
3. Completes payment → Stripe sends webhook to backend
4. Backend verifies webhook → Updates subscription in database
5. Backend restores expired reports for user
6. User redirected to success page → Back to app
7. Subscription status displayed in sidebar
```

## Quick Reference

```bash
# Start backend (with Stripe integration)
cd backend
python -m backend.main

# Start frontend
cd frontend
npm run dev

# Forward webhooks locally
stripe listen --forward-to localhost:8001/api/webhooks/stripe

# View Stripe logs
stripe logs tail

# Test webhook locally
stripe trigger checkout.session.completed
```

---

**All set!** You now have a complete payment infrastructure integrated into your application. Start testing in test mode, then switch to live mode when ready for production.
