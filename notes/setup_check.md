Which file would you change to make /admin say something else?


Answer: templates/admin/hello.html


Where would a new route for posts be registered?


Answer: Create app/routes/posts.py, then in app/main.py add from app.routes import posts and app.include\_router(posts.router)

Why is site/ in .gitignore?  
Answer: generated output from cms publish, not source