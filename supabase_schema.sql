-- Supabase Schema Initialization based on existing Django Models

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table (Maps to Supabase auth.users)
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    phone_number_verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(20) DEFAULT 'INFLUENCER',
    is_banned BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    is_staff BOOLEAN DEFAULT FALSE,
    is_completed_profile BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS for Users
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own profile." ON public.users FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update their own profile." ON public.users FOR UPDATE USING (auth.uid() = id);

-- 2. Categories
CREATE TABLE public.categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Categories are viewable by everyone." ON public.categories FOR SELECT USING (true);

-- 3. Influencers
CREATE TABLE public.influencers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE UNIQUE,
    instagram_username VARCHAR(255),
    pseudo VARCHAR(255),
    biography TEXT,
    site_web TEXT,
    localisation VARCHAR(255),
    instagram_data JSONB DEFAULT '{}'::jsonb,
    langues JSONB DEFAULT '[]'::jsonb,
    centres_interet JSONB DEFAULT '[]'::jsonb,
    type_contenu JSONB DEFAULT '[]'::jsonb,
    disponibilite_collaboration VARCHAR(50) DEFAULT 'disponible',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.influencers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Influencer profiles are viewable by everyone." ON public.influencers FOR SELECT USING (true);
CREATE POLICY "Users can update their own influencer profile." ON public.influencers FOR UPDATE USING (
    EXISTS (SELECT 1 FROM public.users WHERE users.id = auth.uid() AND users.id = influencers.user_id)
);

-- 4. Influencer Categories (Many-to-Many)
CREATE TABLE public.influencer_categories (
    influencer_id UUID REFERENCES public.influencers(id) ON DELETE CASCADE,
    category_id UUID REFERENCES public.categories(id) ON DELETE CASCADE,
    PRIMARY KEY (influencer_id, category_id)
);
ALTER TABLE public.influencer_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Influencer categories are viewable by everyone." ON public.influencer_categories FOR SELECT USING (true);

-- 5. Social Networks (Reseaux Sociaux)
CREATE TABLE public.reseaux_sociaux (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    influencer_id UUID REFERENCES public.influencers(id) ON DELETE CASCADE,
    plateforme VARCHAR(50) NOT NULL,
    url_profil TEXT NOT NULL,
    nombre_abonnes INTEGER DEFAULT 0,
    taux_engagement FLOAT DEFAULT 0.0,
    moyenne_vues INTEGER DEFAULT 0,
    moyenne_likes INTEGER DEFAULT 0,
    moyenne_commentaires INTEGER DEFAULT 0,
    frequence_publication VARCHAR(50) DEFAULT 'hebdomadaire',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (influencer_id, plateforme)
);
ALTER TABLE public.reseaux_sociaux ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Social networks are viewable by everyone." ON public.reseaux_sociaux FOR SELECT USING (true);

-- 6. Offers
CREATE TABLE public.offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    min_budget DECIMAL(10,2) NOT NULL,
    max_budget DECIMAL(10,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    influencer_number INTEGER NOT NULL,
    requirement TEXT NOT NULL,
    objectif TEXT NOT NULL,
    created_by UUID REFERENCES public.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.offers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Offers are viewable by everyone." ON public.offers FOR SELECT USING (true);

-- Trigger to automatically create a user profile when a new auth.users is created
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (id, email, name, role)
  VALUES (new.id, new.email, COALESCE(new.raw_user_meta_data->>'name', 'New User'), 'INFLUENCER');
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- Trigger to automatically updated_at timestamps
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS trigger AS $$
BEGIN
  new.updated_at = NOW();
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER set_updated_at_users
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();

CREATE TRIGGER set_updated_at_influencers
  BEFORE UPDATE ON public.influencers
  FOR EACH ROW EXECUTE PROCEDURE public.handle_updated_at();
