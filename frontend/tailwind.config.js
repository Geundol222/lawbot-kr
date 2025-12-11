/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: '#1f2937',
            a: {
              color: '#3b82f6',
              '&:hover': {
                color: '#2563eb',
              },
            },
            h1: {
              fontWeight: '700',
              fontSize: '1.5rem',
              marginTop: '1rem',
              marginBottom: '0.5rem',
            },
            h2: {
              fontWeight: '600',
              fontSize: '1.25rem',
              marginTop: '1rem',
              marginBottom: '0.5rem',
            },
            h3: {
              fontWeight: '600',
              fontSize: '1.125rem',
              marginTop: '0.75rem',
              marginBottom: '0.5rem',
            },
            ul: {
              marginTop: '0.5rem',
              marginBottom: '0.5rem',
            },
            ol: {
              marginTop: '0.5rem',
              marginBottom: '0.5rem',
            },
            li: {
              marginTop: '0.25rem',
              marginBottom: '0.25rem',
            },
            p: {
              marginTop: '0.5rem',
              marginBottom: '0.5rem',
            },
            blockquote: {
              fontStyle: 'normal',
              fontWeight: '400',
              borderLeftColor: '#3b82f6',
              backgroundColor: '#f1f5f9',
              padding: '0.75rem 1rem',
              marginTop: '0.75rem',
              marginBottom: '0.75rem',
            },
            code: {
              backgroundColor: '#f1f5f9',
              padding: '0.125rem 0.25rem',
              borderRadius: '0.25rem',
              fontWeight: '500',
            },
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
            strong: {
              fontWeight: '700',
              color: '#111827',
            },
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
