import { useRef } from "react";
import { Carousel } from "@mantine/carousel";
import Autoplay from "embla-carousel-autoplay";
import { Text, Title } from "@mantine/core";
import SlideVisual, { type SlideVariant } from "./SlideVisual";
import classes from "./modules/ProjectShowcase.module.css";

// ─────────────────────────────────────────────────────────────────────────────
// Edit this array to control the slideshow. Each entry is one slide.
// These are styled placeholders for now — to use a real screenshot, drop the
// file in `web/public/slides/` and add `image: "/slides/your-file.png"` to a
// slide; it will render in place of the gradient. `bg` is the placeholder
// gradient shown when there's no image.
// ─────────────────────────────────────────────────────────────────────────────
interface Slide {
  title: string;
  caption: string;
  bg: string;
  label: string; // small tag shown on the placeholder
  image?: string; // optional: path under public/, e.g. "/slides/dashboard.png"
  variant: SlideVariant;
}

const SLIDES: Slide[] = [
  {
    title: "Transform Links into Insights",
    caption:
      "A full-stack URL shortener with click analytics — shorten any link and track how it performs in real time.",
    label: "Overview",
    bg: "linear-gradient(135deg, #f5651a 0%, #b23907 100%)",
    variant: "overview"
  },
  {
    title: "Blazing-fast redirects",
    caption:
      "Async FastAPI with Redis-cached lookups serves redirects in single-digit milliseconds, cache miss or hit.",
    label: "Performance",
    bg: "linear-gradient(135deg, #1f6feb 0%, #0a2a66 100%)",
    variant: "speed"
  },
  {
    title: "Built to scale",
    caption:
      "Postgres for durability, an arq worker queue for async click tracking, rate limiting, and fully Dockerized.",
    label: "Architecture",
    bg: "linear-gradient(135deg, #2ea043 0%, #10462a 100%)",
    variant: "scale"
  },
];

export default function ProjectShowcase() {
  // Keep the autoplay instance stable across renders.
  const autoplay = useRef(Autoplay({ delay: 5000, stopOnInteraction: false }));

  return (
    <div className={classes.wrapper}>
      <Carousel
        classNames={{
          root: classes.carousel,
          viewport: classes.viewport,
          container: classes.container,
          slide: classes.slide,
          indicators: classes.indicators,
          indicator: classes.indicator,
        }}
        height="100%"
        withIndicators
        withControls={false}
        emblaOptions={{ loop: true, align: "center" }}
        plugins={[autoplay.current]}
        onMouseEnter={autoplay.current.stop}
        onMouseLeave={autoplay.current.reset}
      >
        {SLIDES.map((slide) => (
          <Carousel.Slide key={slide.title}>
            <div className={classes.slideInner}>
              <div
                className={classes.media}
                style={
                  slide.image
                    ? { backgroundImage: `url(${slide.image})`, backgroundSize: "cover", backgroundPosition: "center" }
                    : { background: "#101218" }
                }
              >
                {slide.image ? null : <span className={classes.mediaLabel}>{slide.label}</span>}
                {!slide.image && <SlideVisual variant={slide.variant} />}
              </div>

              <div className={classes.text}>
                <Title order={2} c="white" fw={700} fz={28} lh={1.15}>
                  {slide.title}
                </Title>
                <Text c="dimmed" size="sm" mt="sm" maw={440}>
                  {slide.caption}
                </Text>
              </div>
            </div>
          </Carousel.Slide>
        ))}
      </Carousel>
    </div>
  );
}
