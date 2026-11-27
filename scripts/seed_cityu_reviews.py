"""Crea usuarios demo extra (demo13-demo22) y reseñas para los restaurantes de City U (ids 5-14).

Es idempotente: no duplica usuarios, reseñas, guardados ni vistas.
Uso: python -m scripts.seed_cityu_reviews [--dry-run]
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import engine
from app.security import hash_password
from scripts.import_sqlite import ImportFailure, require_schema

DEMO_PASSWORD = "Demo1234!"
DEMO_DOMAIN = "@uniandes.edu.co"
NEW_USERS = [
    (13, "Juliana Cardenas"), (14, "Sebastian Rincon"), (15, "Natalia Poveda"),
    (16, "Felipe Bernal"), (17, "Daniela Acosta"), (18, "Camilo Salazar"),
    (19, "Paula Moreno"), (20, "Julian Duarte"), (21, "Manuela Cortes"), (22, "Esteban Lozano"),
]

# restaurant_id -> (base score, [(comentario, dietas)])
REVIEWS = {
    "5": (4.5, [
        ("Los tacos al pastor son lo mejor de City U, la piña le da el toque perfecto.", []),
        ("El burrito es enorme y queda lleno hasta la noche. Muy buen precio.", []),
        ("Atienden rápido incluso en hora pico. Los nachos son para compartir.", ["Vegetarian options"]),
        ("Sabor auténtico, el guacamole es fresco. Faltan más opciones sin carne.", ["Vegetarian options"]),
        ("Voy cada semana después de clase, nunca falla.", []),
    ]),
    "6": (4.4, [
        ("La Tote Classic es jugosa y las papas siempre salen crocantes.", []),
        ("Buena hamburguesa para el precio, la malteada de fresa está muy buena.", []),
        ("A veces hay fila pero avanza rápido. Recomendada la Bacon Tote.", []),
        ("El pollo crispy estaba perfecto, bien sazonado.", []),
        ("Buena opción para un almuerzo rápido entre clases.", []),
    ]),
    "7": (4.2, [
        ("Personal de pepperoni a buen precio, ideal para el almuerzo.", []),
        ("El pan de ajo está delicioso. La pizza a veces llega un poco fría.", []),
        ("Combos pensados para estudiantes, rinden bastante.", []),
        ("Servicio amable, la Hawaiana cumple como siempre.", []),
        ("La personal vegetariana es una buena opción, bastante queso.", ["Vegetarian options"]),
    ]),
    "8": (4.6, [
        ("La Playlera es increíble, el huevo y el tocino le dan mucho sabor.", []),
        ("Me encanta la decoración gamer y los precios son muy buenos.", []),
        ("La salchipapa es enorme, perfecta para dos personas.", []),
        ("Atención súper amable y rápida, repetiría sin dudarlo.", []),
        ("El hot dog Pixel es diferente, con papas trituradas encima. Muy bueno.", []),
    ]),
    "9": (4.3, [
        ("Las alitas BBQ son lo mejor, bien crocantes por fuera y jugosas por dentro.", []),
        ("Las de limón pimienta están buenísimas. Pica poco, se disfruta.", []),
        ("Buen plan para compartir con amigos después de clase.", []),
        ("Las papas con queso son adictivas. Algo caro por la cantidad.", []),
        ("Los boneless son muy buenos, vienen con buen dip.", []),
    ]),
    "10": (4.5, [
        ("El poke de salmón es fresco y la porción es generosa.", ["Gluten-free"]),
        ("Me gusta poder armar mi bowl, el aguacate siempre está en su punto.", ["Vegan options"]),
        ("Opción saludable y rápida, perfecta para el almuerzo.", ["Gluten-free", "Vegan options"]),
        ("El bowl de tofu es sorprendentemente rico. Muy buen servicio.", ["Vegan options", "Vegetarian options"]),
        ("Un poco costoso pero la calidad lo vale.", []),
    ]),
    "11": (4.4, [
        ("El Pad Thai está muy bien hecho, salteado al momento.", []),
        ("Me gusta que el wok se prepare frente a uno. Sabor excelente.", []),
        ("Buena porción de arroz frito vegetariano, económico.", ["Vegetarian options", "Vegan options"]),
        ("El pollo teriyaki es mi favorito, la salsa tiene buen punto dulce.", []),
        ("Hay fila al mediodía pero vale la pena la espera.", []),
    ]),
    "12": (4.7, [
        ("Las crepes de pollo y champiñones son un clásico, nunca fallan.", []),
        ("El waffle con helado es el mejor postre del plazoleta.", []),
        ("Servicio muy amable y todo muy fresco, siempre de calidad.", ["Vegetarian options"]),
        ("Un poco más caro que el resto, pero la calidad se nota.", []),
        ("La crepe vegetariana viene muy completa. Recomendada.", ["Vegetarian options"]),
    ]),
    "13": (4.1, [
        ("Excelente para gastar poco, la caja de pollo rinde mucho.", []),
        ("Almuerzo rápido y económico, justo lo que necesito entre clases.", []),
        ("La caja vegetariana está bien, pero podría tener más variedad.", ["Vegetarian options"]),
        ("Buen sabor casero. La limonada con menta es muy refrescante.", []),
        ("Atención rápida, ideal si tienes poco tiempo.", []),
    ]),
    "14": (4.6, [
        ("La Cacio e Pepe hecha en la rueda de queso es un espectáculo y está deliciosa.", ["Vegetarian options"]),
        ("La carbonara es cremosa y muy bien sazonada, porción generosa.", []),
        ("Perfecto para una ocasión especial dentro de la universidad.", []),
        ("La tabla de quesos es ideal para compartir. Algo cara pero vale la pena.", ["Vegetarian options"]),
        ("El alfredo con pollo estaba increíble y el servicio fue muy atento.", []),
    ]),
}


def clamp(value: float) -> int:
    return max(1, min(5, round(value)))


def run(dry_run: bool) -> int:
    with engine.connect() as probe:
        require_schema(probe)
    rng = random.Random(2026)
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    password_hash = hash_password(DEMO_PASSWORD)
    counts = {"users": 0, "reviews": 0, "saved": 0, "views": 0}
    with Session(engine) as session:
        known = {r.id for r in session.scalars(select(models.Restaurant))}
        missing = [rid for rid in REVIEWS if rid not in known]
        if missing:
            raise ImportFailure(f"Faltan restaurantes {missing}. Ejecuta: alembic upgrade head")

        for index, name in NEW_USERS:
            email = f"demo{index:02d}{DEMO_DOMAIN}"
            if session.scalar(select(models.User).where(models.User.email == email)) is None:
                session.add(models.User(
                    email=email, name=name, password_hash=password_hash,
                    created_at=now - timedelta(days=rng.randint(30, 60)),
                ))
                counts["users"] += 1
        session.flush()

        users = list(session.scalars(
            select(models.User).where(models.User.email.like(f"demo%{DEMO_DOMAIN}")).order_by(models.User.id)
        ))
        if len(users) < 5:
            raise ImportFailure("No hay suficientes usuarios demo")

        for position, (rid, (base, items)) in enumerate(REVIEWS.items()):
            for offset, (comment, dietary) in enumerate(items):
                user = users[(position * 3 + offset * 2) % len(users)]
                exists = session.scalar(select(models.Review).where(
                    models.Review.user_id == user.id, models.Review.restaurant_id == rid))
                created = now - timedelta(days=rng.uniform(0, 42), hours=rng.uniform(0, 8))
                if exists is None:
                    session.add(models.Review(
                        restaurant_id=rid, user_id=user.id,
                        taste=clamp(base + rng.uniform(-0.4, 0.6)),
                        attention=clamp(base + rng.uniform(-0.6, 0.5)),
                        price=clamp(base + rng.uniform(-0.9, 0.4)),
                        options=clamp(base - 0.5 + rng.uniform(-0.8, 0.8)),
                        dietary_options=dietary, comment=comment[:300], created_at=created,
                    ))
                    counts["reviews"] += 1
                if offset < 2:
                    if session.get(models.SavedRestaurant, (user.id, rid)) is None:
                        session.add(models.SavedRestaurant(
                            user_id=user.id, restaurant_id=rid, saved_at=created.replace(tzinfo=timezone.utc)))
                        counts["saved"] += 1
                if session.scalar(select(models.RestaurantView).where(
                        models.RestaurantView.user_id == user.id,
                        models.RestaurantView.restaurant_id == rid)) is None:
                    session.add(models.RestaurantView(
                        user_id=user.id, restaurant_id=rid,
                        viewed_at=(created - timedelta(minutes=rng.randint(1, 30))).replace(tzinfo=timezone.utc)))
                    counts["views"] += 1
            session.flush()

        if dry_run:
            session.rollback()
        else:
            session.commit()
    for key, total in counts.items():
        print(f"{key:<10} {total}")
    print("SIMULACION (no se escribio nada)" if dry_run else "RESEÑAS DE CITY U CREADAS")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Siembra usuarios y reseñas demo para City U")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run(args.dry_run)
    except ImportFailure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
