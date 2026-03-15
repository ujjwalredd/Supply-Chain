// Vercel Edge Function — receives design partner form submissions
// and sends a notification email via Resend.
//
// Setup:
//   1. npm install resend  (in the modern-landing directory)
//   2. Go to https://resend.com, create a free account
//   3. Get your API key → add to Vercel env vars as RESEND_API_KEY
//   4. In DesignPartner.tsx set FORM_ENDPOINT = "/api/contact"
//
// Resend free tier: 100 emails/day, 3,000/month — enough for early stage.

import type { VercelRequest, VercelResponse } from '@vercel/node';

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Only POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { name, company, email, problem } = req.body ?? {};

  if (!name || !company || !email || !problem) {
    return res.status(400).json({ error: 'All fields are required.' });
  }

  // Basic email format check
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Invalid email address.' });
  }

  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.error('RESEND_API_KEY not set');
    return res.status(500).json({ error: 'Server configuration error.' });
  }

  // Replace with your verified Resend sender domain
  // (use onboarding@resend.dev for testing before you verify a domain)
  const FROM = process.env.FROM_EMAIL ?? 'onboarding@resend.dev';
  const TO   = process.env.TO_EMAIL   ?? 'ujjwalreddyks@gmail.com'; // your email

  const payload = {
    from: FROM,
    to: TO,
    reply_to: email,
    subject: `[ForeverAutonomous] New Design Partner: ${company}`,
    html: `
      <div style="font-family:monospace;max-width:560px;margin:0 auto;padding:24px;background:#fafafa;border-radius:12px;border:1px solid #e4e4e7">
        <h2 style="margin:0 0 16px;font-size:18px;color:#09090b">New Design Partner Application</h2>
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:8px 0;color:#71717a;font-size:12px">NAME</td>    <td style="padding:8px 0;color:#09090b">${escapeHtml(name)}</td></tr>
          <tr><td style="padding:8px 0;color:#71717a;font-size:12px">COMPANY</td> <td style="padding:8px 0;color:#09090b">${escapeHtml(company)}</td></tr>
          <tr><td style="padding:8px 0;color:#71717a;font-size:12px">EMAIL</td>   <td style="padding:8px 0;color:#0070f3"><a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></td></tr>
        </table>
        <div style="margin-top:16px;padding:12px 16px;background:#fff;border-radius:8px;border:1px solid #e4e4e7">
          <p style="margin:0 0 6px;color:#71717a;font-size:12px">PROBLEM STATEMENT</p>
          <p style="margin:0;color:#09090b;line-height:1.6">${escapeHtml(problem)}</p>
        </div>
        <p style="margin-top:16px;font-size:11px;color:#a1a1aa">
          Submitted at ${new Date().toISOString()} via ForeverAutonomous landing page
        </p>
      </div>
    `,
  };

  const response = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = await response.text();
    console.error('Resend error:', err);
    return res.status(500).json({ error: 'Failed to send email. Please try again.' });
  }

  return res.status(200).json({ ok: true });
}

function escapeHtml(str: string) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
