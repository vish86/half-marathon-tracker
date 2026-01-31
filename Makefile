VENV=.venv/bin/activate

update:
	@if [ -z "$(TYPE)" ]; then echo "TYPE missing (easy|long|threshold)"; exit 1; fi
	@if [ -z "$(FILE)" ]; then echo "FILE missing"; exit 1; fi
	@if [ -z "$(DATE)" ]; then echo "DATE missing (YYYY-MM-DD)"; exit 1; fi
	@echo "Adding run: $(TYPE) $(DATE)"
	@source $(VENV) && \
	mv $(FILE) data/raw/$(TYPE)/$(DATE).fit && \
	python src/parse_fit.py && \
	python src/update_readme.py && \
	git add README.md data/raw && \
	git commit -m "run: $(DATE) $(TYPE) + update goal status" && \
	git push
