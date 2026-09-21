"""Run the integrated YouTube-first idea research without spending model credits."""
import argparse
import json

from pipeline.production import refresh_sources, research_video_ideas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-news', action='store_true', help='Also refresh/enrich current news feeds')
    parser.add_argument('--force-youtube', action='store_true', help='Bypass the six-hour API metadata cache')
    args = parser.parse_args()
    if args.refresh_news:
        print(json.dumps(refresh_sources(), indent=2))
    print(json.dumps(research_video_ideas(force_youtube=args.force_youtube), indent=2))


if __name__ == '__main__':
    main()
