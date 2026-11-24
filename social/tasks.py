from celery import shared_task
from social.models import Post


@shared_task
def publish_scheduled_post(post_id: int) -> str:
    """Публікує відкладений пост у призначений час."""
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return f"Post #{post_id} not found (possibly deleted before publishing)."

    if not post.is_published:
        post.is_published = True
        post.save(update_fields=["is_published"])
        return f"Post #{post_id} successfully published."

    return f"Post #{post_id} was already published."
