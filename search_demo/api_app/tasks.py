from celery import shared_task
import suggestion_cache_builder


@shared_task
def rebuild_suggestion_cache(site_id):
    suggestion_cache_builder.rebuild_suggestion_cache(site_id)


@shared_task
def rebuild_hot_keywords(site_id):
    hot_keywords_builder.rebuild_hot_keywords(site_id)
