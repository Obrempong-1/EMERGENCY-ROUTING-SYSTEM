import type { Metadata } from 'next';
import CreatorContent from './CreatorContent';

export const metadata: Metadata = {
    title: 'Obrempong Kwabena Osei-Wusu | Developer',
    description: 'Geomatic Engineering Student & Backend Engineer behind KNUST Response.',
    openGraph: {
        title: 'Obrempong Kwabena Osei-Wusu',
        description: 'Geomatic Engineering Student & Backend Engineer. Check out my work on KNUST Response.',
        url: 'https://knustgisemergencysystem.vercel.app/creator',
        siteName: 'KNUST Response',
        images: [
            {
                url: '/Obrempong.jpg',
                width: 800,
                height: 600,
                alt: 'Obrempong Kwabena Osei-Wusu',
            },
        ],
        locale: 'en_US',
        type: 'profile',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'Obrempong Kwabena Osei-Wusu',
        description: 'Geomatic Engineering Student & Backend Engineer.',
        images: ['/Obrempong.jpg'],
    },
};

export default function CreatorPage() {
    return <CreatorContent />;
}
